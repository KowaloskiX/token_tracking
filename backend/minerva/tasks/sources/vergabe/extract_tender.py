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

# ──────────────────────────────────────────────────────────────────────────────
#  default root-url → source_type mapping
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_PAGE_TYPE_MAP: dict[str, str] = {
    "https://www.dtvp.de/Center": "dtvp",
    "https://evergabe.nrw.de/VMPCenter": "evergabe_nrw",
    "https://ausschreibungen.landbw.de/Center": "Baden-Württemberg",
    "https://evergabe-mv.de/Satellite": "Mecklenburg-Vorpommern",
    "https://landesverwaltung.vergabe.rlp.de/VMPSatellite": "RLP Landesverwaltung",
    "https://rlp.vergabekommunal.de/Satellite": "RLP Kommunal",
    "https://vergabe.ihk.de/Satellite": "IHK Vergabe",
    "https://vergabe.niedersachsen.de/Satellite": "Niedersachsen",
    "https://vergabe.tk.de/Satellite": "Thüringen",
    "https://vergabemarktplatz.brandenburg.de/VMPCenter": "Brandenburg",
    "https://www.vergabe.metropoleruhr.de/VMPSatellite": "Metropole Ruhr",
    "https://www.vergaben-wirtschaftsregion-aachen.de/VMPSatellite": "Wirtschaftsregion Aachen",
    "https://www.vergabe-westfalen.de/VMPSatellite": "Westfalen",
    "https://vmp-rheinland.de/VMPSatellite": "Rheinland",
    "https://www.vergabe.rlp.de/VMPCenter": "Vergabe Rheinland-Pfalz",
    "https://vergabe.hilgmbh.de/VMPCenter": "HIL GmbH",
    "https://vergabeportal-bw.de/Satellite": "VergabePortal BW"
}

class DTVPLikeTenderExtractor():
    """
    Scraper for tenders listed in the DTVP extended search
    ( https://www.dtvp.de/Center/common/project/search.do?method=showExtendedSearch&fromExternal=true )
    The table layout and detail pages are almost identical to evergabe.nrw,
    but there are no CPV-category pages – only one global result list that
    must be paginated.
    """

    def __init__(self, page_type_map: Optional[dict[str, str]] = None, fallback_source_type: str = "dtvp_like"):
        self.page_type_map: dict[str, str] = (
            page_type_map if page_type_map is not None else DEFAULT_PAGE_TYPE_MAP
        )
        self.root_pages: List[str] = list(self.page_type_map.keys())
        self._fallback_source_type = fallback_source_type
        self.source_type = fallback_source_type
        # Add URL tracking
        self.url_tracking = {}  # source_type -> set of URLs
        self.unique_urls = set()  # Track all unique URLs across all sources

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
        max_pages      = inputs.get("max_pages", 50)
        start_dt       = None
        start_date_str = inputs.get("start_date")
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                logging.error(f"{self.source_type}: invalid start_date '{start_date_str}'")

        tenders: List[Tender] = []
        pages_visited = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()

                for root in self.root_pages:
                    pages_visited = 0
                    self.source_type = self.page_type_map.get(root, self._fallback_source_type)
                    # Initialize URL tracking for this source type
                    self.url_tracking[self.source_type] = set()
                    
                    root += "/common/project/search.do?method=showExtendedSearch&fromExternal=true"
                    logging.info(f"[{self.source_type}] Processing root: {root}")
                    tenders_before = len(tenders)

                    page = await context.new_page()
                    try:
                        await self._goto_with_retry(page, root)
                    except Exception as e:
                        logging.error(f"Error loading page: {root} {e}")
                        continue

                    if self.source_type == "dtvp":
                        # cookie banner (appears only once per session)
                        try:
                            await page.wait_for_selector(".ccm-modal-inner", timeout=4_000)
                            btn = await page.query_selector("button.ccm--save-settings[data-full-consent='true']")
                            if btn:
                                await btn.click()
                                await page.wait_for_timeout(800)
                                logging.debug(f"{self.source_type}: cookie banner accepted")
                        except Exception:
                            pass

                        try:
                            if not await page.query_selector("table tbody tr"):
                                await page.click("input#searchStart")
                                await page.wait_for_load_state("networkidle")
                        except Exception:
                            pass

                    await page.wait_for_timeout(500)
                    try:
                        # sort by publication date DESC (two clicks toggles ASC → DESC)
                        for _ in range(2):
                            if "Satellite" in root:
                                link = await page.query_selector("th a.waitClick[onclick*='publicationDate']")
                            else:
                                link = await page.query_selector("th a#publicationDate.sortable")
                            if link:
                                await link.click()
                                await page.wait_for_load_state("networkidle")
                                await page.wait_for_timeout(500)
                    except Exception:
                        pass

                    await page.wait_for_timeout(500)
                    # paginate through list
                    stop_root = False
                    while not stop_root and pages_visited < max_pages:
                        pages_visited += 1
                        logging.info(f"{self.source_type}: processing list page {pages_visited}")

                        # Wait until at least one result row is present *after* possible
                        # Ajax refresh; prevents invalid handles later.
                        if "Satellite" in root:
                            await page.wait_for_selector("table.csx-new-table tbody tr")
                        else:
                            await page.wait_for_selector("tbody tr")

                        row_handles = await page.query_selector_all("tbody tr")  # fresh each loop
                        for row in row_handles:
                            try:
                                # ---- publication date ---------------------------------
                                if "Satellite" in root:
                                    pub_title = await row.eval_on_selector(
                                        "td:nth-child(1) abbr", "el => el.title || ''"
                                    )
                                else:
                                    pub_title = await row.eval_on_selector(
                                        "td:nth-child(1) abbr", "el => el.title || ''"
                                    )
                                if not pub_title:
                                    continue
                                try:
                                    pub_date = datetime.strptime(
                                        pub_title, "%d.%m.%Y um %H:%M Uhr"
                                    ).date()
                                except ValueError:
                                    pub_date = None
                                if start_dt and pub_date and pub_date < start_dt:
                                    stop_root = True
                                    break

                                # ---- quick extraction of the remaining visible cols ----
                                if "Satellite" in root:
                                    name = (await row.eval_on_selector(
                                        "td:nth-child(3)", "el => el.innerText.trim()"
                                    )) or ""
                                    org_name = (await row.eval_on_selector(
                                        "td:nth-child(5)", "el => el.innerText.trim()"
                                    )) or ""
                                else:
                                    name = (await row.eval_on_selector(
                                        "td:nth-child(3)", "el => el.innerText.trim()"
                                    )) or ""
                                    org_name = (await row.eval_on_selector(
                                        "td:nth-child(5)", "el => el.innerText.trim()"
                                    )) or ""

                                # href: javascript:openProjectPopup('https://...pid=123', '123');
                                if "Satellite" in root:
                                    href_js = await row.eval_on_selector(
                                        "td:nth-child(6) a",
                                        "el => el.getAttribute('href') || ''"
                                    )
                                    m_href = re.search(r"openProjectPopup\('([^']+)',", href_js)
                                    if not m_href:
                                        continue
                                    detail_url = m_href.group(1)
                                    if not detail_url.startswith('http'):
                                        # Handle relative URLs for Satellite
                                        if "VMPSatellite" in root:
                                            base_url = root.split('/VMPSatellite')[0]
                                        else:
                                            base_url = root.split('/Satellite')[0]
                                        detail_url = base_url + detail_url
                                else:
                                    href_js = await row.eval_on_selector(
                                        "td:nth-child(6) a",
                                        "el => el.getAttribute('href') || ''"
                                    )
                                    m_href = re.search(r"openProjectPopup\('([^']+)',", href_js)
                                    if not m_href:
                                        continue
                                    detail_url = m_href.group(1)

                                # Track URL
                                self.url_tracking[self.source_type].add(detail_url)
                                if detail_url not in self.unique_urls:
                                    self.unique_urls.add(detail_url)

                            except Exception as e:
                                # Any failure while inspecting this row – skip it, keep going
                                logging.debug(f"{self.source_type}: skipped one row – {e}")
                                continue

                            # ---- visit detail page for location + deadline ----------
                            detail_info = await self.fetch_detail_info(context, detail_url)
                            if detail_info.get("skip"):
                                continue

                            tender_data = {
                                "name": name,
                                "organization": org_name,
                                "location": detail_info.get("location", ""),
                                "submission_deadline": detail_info.get("submission_deadline", ""),
                                "initiation_date": pub_date.strftime("%Y-%m-%d") if pub_date else "",
                                "details_url": detail_url,
                                "content_type": "tender",
                                "source_type": self._fallback_source_type,
                            }
                            try:
                                tenders.append(Tender(**tender_data))
                                logging.info(f"{self.source_type}: scraped tender '{name}'")
                            except Exception as e:
                                logging.error(f"{self.source_type}: could not build Tender – {e}")

                        # ---- next page ---------------------------------------------
                        if stop_root or pages_visited >= max_pages:
                            break
                        if "Satellite" in root:
                            nxt = await page.query_selector("a.browseForward.waitClick")
                        else:
                            nxt = await page.query_selector(".browseForward:not(.browseForwardGhost)")
                        if nxt:
                            await nxt.click()
                            await page.wait_for_load_state("networkidle")
                        else:
                            break  # reached the last result page

                    await page.close()
                    # Log tenders scraped for this source type
                    tenders_after = len(tenders)
                    tenders_scraped = tenders_after - tenders_before
                    logging.info(f"[{self.source_type}] Scraped {tenders_scraped} tenders from {root}")

                metadata = ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=pages_visited,
                )
                # Log summary of tenders per source type
                source_type_counts = {}
                for tender in tenders:
                    source_type_counts[tender.source_type] = source_type_counts.get(tender.source_type, 0) + 1
                for source_type, count in source_type_counts.items():
                    logging.info(f"[{source_type}] Total tenders scraped: {count}")

                # Print URL tracking summary
                logging.info("=== URL Tracking Summary ===")
                for source_type, urls in self.url_tracking.items():
                    total_urls = len(urls)
                    unique_urls = sum(1 for url in urls if url in self.unique_urls)
                    duplicate_urls = total_urls - unique_urls
                    logging.info(f"Source Type: {source_type}")
                    logging.info(f"Total URLs: {total_urls}")
                    logging.info(f"Unique URLs: {unique_urls}")
                    logging.info(f"Duplicate URLs: {duplicate_urls}")
                logging.info(f"Total unique URLs across all sources: {len(self.unique_urls)}")
                logging.info("========================\n")

                return {"tenders": tenders, "metadata": metadata}
            
            except Exception as e:
                logging.error(f"Error scraping {self._fallback_source_type}: {e}")
                return {"tenders": tenders, "metadata": ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=pages_visited,)
                    }

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
                    btn = await page.query_selector("a:has-text('Teilnahmeunterlagen')")

                    if btn:
                        await btn.click()
                        await page.wait_for_load_state('networkidle')
                    else:

                        logging.info(f"No 'Vergabeunterlagen' or 'Teilnahmeunterlagen' section at {details_url}")
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