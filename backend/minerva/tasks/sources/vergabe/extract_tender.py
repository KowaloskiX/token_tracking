import logging
import re
import os
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from typing import Dict, List, Tuple, Optional
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from playwright.async_api import async_playwright
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender


class EvergabeNRWTenderExtractor:
    """
    Scraper for tenders from the NRW eVergabe platform with category-based listings.
    Iterates through CPV categories, sorts by publication date, paginates globally,
    and fetches location & submission deadline from each tender's detail page,
    handling both German and English layouts.
    max_pages limits total pages visited.
    """

    def __init__(self, source_type: str = "vergabe"):
        self.category_url = (
            "https://evergabe.nrw.de/VMPCenter/company/announcements/categoryOverview.do?"
            "method=showCategoryOverview"
        )
        self.base = "https://evergabe.nrw.de"
        self.source_type = source_type

    async def _goto_with_retry(self, page, url: str, wait_until: str = 'networkidle', timeout: int = 30000, retries: int = 2):
        for attempt in range(retries + 1):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return
            except Exception as e:
                if "Timeout" in str(e) and attempt < retries:
                    logging.info(f"Retrying to load URL for {self.source_type}: {url}")
                else:
                    logging.error(f"Error loading URL for {self.source_type}: {url}: {e}")
                    raise

    def standardize_deadline(self, raw: str) -> str:
        raw = raw.strip().lower()
        if not raw or raw.startswith("nv") or "nicht vorhanden" in raw:
            return ""
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4}).*?(\d{2}):(\d{2})", raw)
        if m:
            day, month, year, hour, minute = m.groups()
            dt = datetime(int(year), int(month), int(day), int(hour), int(minute))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        m2 = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
        if m2:
            day, month, year = m2.groups()
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        return ""

    async def fetch_detail_info(self, context, detail_url: str) -> dict:
        page = await context.new_page()
        info = {"location": "", "submission_deadline": "", "skip": False}
        try:
            await self._goto_with_retry(page, detail_url)

            awarded_text = (
                "Bitte beachten Sie, dass dieser Auftrag bereits vergeben wurde "
                "und Vergabeunterlagen an dieser Stelle nicht mehr abgerufen werden können."
            )
            try:
                page_text = await page.inner_text("div#content")
                if awarded_text in page_text:
                    logging.info(f"{self.source_type}: already awarded, skipping {detail_url}")
                    await page.close()
                    return {"location": "", "submission_deadline": "", "skip": True}
            except Exception:
                logging.debug("Could not check awarded-text, continuing fetch_detail_info")

            # FIRST: grab submission deadline from overview section
            dl_el = await page.query_selector(
                "div.sub-headline-container:has(h4.sub-headline:has-text('Abgabefrist')) + div.control-group"
            ) or await page.query_selector(
                "div.sub-headline-container:has(h4.sub-headline:has-text('Submission deadline')) + div.control-group"
            )
            if dl_el:
                raw = (await dl_el.inner_text()).strip()
                info['submission_deadline'] = self.standardize_deadline(raw)
            else:
                logging.debug(f"No submission deadline element at {detail_url}")

            # THEN: navigate to 'Verfahrensangaben' tab for location if present
            if await page.query_selector("a:has-text('Verfahrensangaben')"):
                await page.click("a:has-text('Verfahrensangaben')")
                await page.wait_for_load_state('networkidle')

            city_el = await page.query_selector("label.control-label:has-text('Ort') + .controls .read-only")
            if city_el:
                info['location'] = (await city_el.inner_text()).strip()
            else:
                # English variant
                city_el_en = await page.query_selector("label.control-label:has-text('Place') + .controls .read-only")
                info['location'] = (await city_el_en.inner_text()).strip() if city_el_en else ""

        except Exception as e:
            logging.error(f"Error fetching detail for {self.source_type} at {detail_url}: {e}")
        finally:
            await page.close()
        return info



    async def execute(self, inputs: Dict) -> Dict:
        max_pages = inputs.get("max_pages", 50)
        start_date_str = inputs.get("start_date")
        start_dt = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except:
                logging.error(f"Invalid start_date format: {start_date_str}")

        tenders = []
        pages_visited = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()
                await self._goto_with_retry(page, self.category_url)
                cat_links = await page.query_selector_all("table tbody tr td a[title^='CPV-Code']")
                category_urls = [self.base + await a.get_attribute('href') for a in cat_links]
                await page.close()

                for cat_url in category_urls:
                    if pages_visited >= max_pages:
                        break
                    page = await context.new_page()
                    await self._goto_with_retry(page, cat_url)
                    # sort by publication date descending
                    for _ in range(2):
                        link = await page.query_selector(
                            'th a[onclick*="tableSortAttributePROJECT_RESULT=publicationDate"]'
                        )
                        if link:
                            await link.click()
                            await page.wait_for_timeout(1000)

                    stop_cat = False
                    while pages_visited < max_pages and not stop_cat:
                        pages_visited += 1
                        rows = await page.query_selector_all("tbody tr")
                        for row in rows:
                            pub_el = await row.query_selector("td:nth-child(1) abbr")
                            if not pub_el:
                                continue
                            pub_title = await pub_el.get_attribute("title")
                            try:
                                pub_date = datetime.strptime(pub_title, "%d.%m.%Y um %H:%M Uhr").date()
                            except:
                                pub_date = None
                            if start_dt and pub_date and pub_date < start_dt:
                                stop_cat = True
                                break
                            title_el = await row.query_selector("td:nth-child(3)")
                            org_el = await row.query_selector("td:nth-child(5)")
                            link_el = await row.query_selector("td:nth-child(6) a")
                            if not all([title_el, org_el, link_el]):
                                continue
                            name = (await title_el.inner_text()).strip()
                            org_name = (await org_el.inner_text()).strip()
                            href = await link_el.get_attribute("href")
                            pidm = re.search(r"pid=(\d+)", href)
                            pid = pidm.group(1) if pidm else ''
                            detail_url = f"{self.base}/VMPCenter/public/company/projectForwarding.do?pid={pid}"

                            detail_info = await self.fetch_detail_info(context, detail_url)
                            if detail_info.get("skip"):
                                # skip this tender entirely
                                continue
                            tender_data = {
                                "name": name,
                                "organization": org_name,
                                "location": detail_info.get("location", ""),
                                "submission_deadline": detail_info.get("submission_deadline", ""),
                                "initiation_date": pub_date.strftime("%Y-%m-%d") if pub_date else "",
                                "details_url": detail_url,
                                "content_type": "tender",
                                "source_type": self.source_type,
                            }
                            try:
                                tenders.append(Tender(**tender_data))
                                logging.info(f"Scraped tender: {name}")
                            except Exception as e:
                                logging.error(f"Error creating Tender: {e}")
                        if stop_cat:
                            break
                        nxt = await page.query_selector(".browseForward:not(.browseForwardGhost)")
                        if nxt:
                            await nxt.click()
                            await page.wait_for_timeout(1000)
                        else:
                            break
                    await page.close()

                metadata = ExtractorMetadata(total_tenders=len(tenders), pages_scraped=pages_visited)
                return {"tenders": tenders, "metadata": metadata}
            finally:
                await browser.close()

    async def extract_files_from_detail_page(
        self,
        context,
        details_url: str
    ) -> List[Tuple[bytes, str, Optional[str]]]:
        """
        Extract attachments from the detail page AND save the page's textual description
        as a separate .txt file. Returns a list of (file_content, filename, download_url).
        """
        page = await context.new_page()
        processed_files: List[Tuple[bytes, str, Optional[str]]] = []
        service = FileExtractionService()
        temp_dir = None
        try:
            await self._goto_with_retry(page, details_url)
            # navigate to Vergabeunterlagen if available
            try:
                btn = await page.query_selector("a:has-text('Vergabeunterlagen')")
                if btn:
                    await btn.click()
                    await page.wait_for_load_state('networkidle')
                else:
                    logging.info(f"No 'Vergabeunterlagen' section at {details_url}")
                    return []
            except Exception as e:
                logging.error(f"Error clicking Vergabeunterlagen at {details_url}: {e}")
                return []

            # prepare temp dir
            unique = uuid4().hex
            temp_dir = Path.cwd() / "temp_files" / unique
            temp_dir.mkdir(parents=True, exist_ok=True)
            try:
                zip_btn = await page.query_selector("a.btn[href*='archive']")
                if zip_btn:
                    download_url = await zip_btn.get_attribute('href')
                    from urllib.parse import urljoin
                    full_url = urljoin(details_url, download_url)
                    # use playwright download
                    async with page.expect_download() as dl_info:
                        await zip_btn.click()
                    download = await dl_info.value
                    out_path = temp_dir / download.suggested_filename
                    await download.save_as(str(out_path))
                    for file_content, filename, preview_chars, original_bytes, original_filename in await service.process_file_async(out_path):
                        processed_files.append(
                                (file_content, filename, full_url, preview_chars, original_bytes)
                            )
                        logging.info(f"Downloaded and processed archive {filename}")
                else:
                    logging.info(f"No archive ZIP button at {details_url}")
            except Exception as e:
                logging.error(f"Error downloading archive ZIP at {details_url}: {e}")
        except Exception as e:
            logging.error(f"Error in file extraction at {details_url}: {e}")
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            await page.close()
        return processed_files
