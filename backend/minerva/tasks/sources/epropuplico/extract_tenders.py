import logging
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from playwright.async_api import async_playwright
from minerva.core.utils.date_standardizer import DateStandardizer
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender


class EproPublicoMainTenderExtractor:
    """
    A tender extractor for scraping the main listing page of e-propublico.pl/Ogloszenia
    (i.e., NOT restricted to a specific organization).
    """
    def __init__(
        self,
        source_type: str = "epropublico_main"
    ):
        self.base_list_url = "https://e-propublico.pl/Ogloszenia"
        self.source_type = source_type

    async def _goto_with_retry(
        self,
        page,
        url: str,
        wait_until: str,
        timeout: int,
        retries: int = 2,
        purpose: str = "navigation"
    ):
        for attempt in range(retries + 1):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return
            except Exception as e:
                if attempt < retries:
                    logging.info(f"{self.source_type}: Retrying to load URL: {url} (attempt {attempt+1})")
                else:
                    logging.error(f"{self.source_type}: Timeout/error loading URL: {url}")
                    raise e

    async def fetch_detail_info(
        self,
        context,
        detail_url: str
    ) -> dict:
        page = await context.new_page()
        detail_info = {
            "publication_dt": None,
            "org_name": "Unknown",
            "location": "",
        }
        try:
            await self._goto_with_retry(page, detail_url, wait_until='networkidle', timeout=15000, retries=2, purpose="fetch detail")
            # Parse the card body for organization and location info
            card_body = await page.query_selector("div.card-body")
            if card_body:
                org_name_elem = await card_body.query_selector("h6.card-title")
                if org_name_elem:
                    detail_info["org_name"] = (await org_name_elem.inner_text()).strip()
                divs_after_title = await card_body.query_selector_all("div")
                lines = [(await d.inner_text()).strip() for d in divs_after_title]
                address_lines = []
                for line in lines:
                    if any(keyword in line.lower() for keyword in ["tel.:", "faks:", "e-mail:", "adres strony internetowej"]):
                        break
                    address_lines.append(line)
                if address_lines:
                    detail_info["location"] = ", ".join(address_lines)
            # Look for publication date in candidate elements
            possible_elems = await page.query_selector_all(
                "div.row div.col-md-12, div.row div.col-lg-6, div.row div.col-xl-5"
            )
            for elem in possible_elems:
                text = (await elem.inner_text()).strip()
                if "Data publikacji" in text:
                    parts = text.split("Data publikacji:")
                    if len(parts) > 1:
                        dt_str = parts[1].strip()
                        try:
                            publication_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                            detail_info["publication_dt"] = publication_dt
                            break
                        except ValueError:
                            logging.error(f"{self.source_type}: Could not parse publication date string: {dt_str}")
                    else:
                        logging.error(f"{self.source_type}: No date found after 'Data publikacji:'")
        except Exception as e:
            logging.error(f"{self.source_type}: Error fetching detail info from {detail_url}: {str(e)}")
        finally:
            await page.close()
        return detail_info

    async def extract_files_from_detail_page(
        self,
        context,
        details_url: str
    ) -> List[Tuple[bytes, str, Optional[str]]]:
        page = await context.new_page()
        processed_files = []
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        temp_dir = None
        try:
            await self._goto_with_retry(page, details_url, wait_until='networkidle', timeout=15000, retries=2, purpose="extract files")
            doc_tab_link = await page.query_selector("#navItem_dokumentyZamowienia")
            if not doc_tab_link:
                logging.info(f"{self.source_type}: No 'Dokumenty zamówienia' link found at {details_url}.")
                return processed_files
            async with page.expect_navigation(timeout=15000):
                await doc_tab_link.click()
            await page.wait_for_selector("table#checkable tbody tr", timeout=15000)

            
            unique_id = str(uuid4())
            temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
            temp_dir.mkdir(parents=True, exist_ok=True)

            rows = await page.query_selector_all("table#checkable tbody tr")
            if not rows:
                logging.info(f"{self.source_type}: No document rows found at {details_url}.")
                return processed_files
            for row in rows:
                try:
                    link = await row.query_selector("a[href*='/Dokumenty/Download/']")
                    if not link:
                        continue
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    download_url = "https://e-propublico.pl" + href
                    async with page.expect_download(timeout=15000) as download_info:
                        await link.click()
                        download = await download_info.value
                    suggested_name = download.suggested_filename or "document"
                    temp_path = temp_dir / suggested_name
                    await download.save_as(str(temp_path))
                    file_results = await extraction_service.process_file_async(temp_path)
                    for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results:
                        processed_files.append((file_content, filename, download_url, preview_chars, original_bytes))
                except Exception as e:
                    logging.error(f"{self.source_type}: Error downloading file from {details_url}: {str(e)}")
                    continue
            logging.info(f"{self.source_type}: Processed {len(processed_files)} files from {details_url}")
        except Exception as e:
            logging.error(f"{self.source_type}: Error accessing detail page {details_url}: {str(e)}")
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            await page.close()
        return processed_files

    async def execute(self, inputs: Dict) -> Dict:
        """
        Main method to run the scraper.
         - max_pages: how many listing pages to traverse
         - start_date: skip any tenders published before this date (YYYY-MM-DD)
        """
        max_pages = inputs.get("max_pages", 10)
        start_date_str = inputs.get("start_date", None)
        start_dt = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                logging.info(f"{self.source_type}: Starting extraction with start_date: {start_date_str}")
            except ValueError:
                logging.error(f"{self.source_type}: Invalid date format for start_date: {start_date_str}")
                start_dt = None
        else:
            logging.info(f"{self.source_type}: Starting extraction with no start_date.")
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                tenders = []
                current_page = 1
                # Iterate over listing pages
                while current_page <= max_pages:
                    list_url = f"{self.base_list_url}?page={current_page}"
                    page = await context.new_page()
                    try:
                        logging.info(f"{self.source_type}: Navigating to listing page: {list_url}")
                        await self._goto_with_retry(page, list_url, wait_until='networkidle', timeout=15000, retries=2, purpose="list page")
                    except Exception as e:
                        logging.error(f"{self.source_type}: Error navigating to {list_url}: {str(e)}")
                        await page.close()
                        break
                    table = await page.query_selector("table.table")
                    if not table:
                        logging.info(f"{self.source_type}: No tenders table found on page={current_page}. Stopping.")
                        await page.close()
                        break
                    rows = await table.query_selector_all("tbody tr")
                    if not rows:
                        logging.info(f"{self.source_type}: No rows found on page={current_page}. Stopping.")
                        await page.close()
                        break
                    found_recent = False
                    for row in rows:
                        try:
                            cells = await row.query_selector_all("td")
                            if len(cells) < 4:
                                continue
                            signature = (await cells[0].inner_text()).strip()
                            name_link = await cells[1].query_selector("a")
                            name = (await cells[1].inner_text()).strip()
                            detail_url = ""
                            if name_link:
                                details_href = await name_link.get_attribute("href")
                                if details_href:
                                    if details_href.startswith("/"):
                                        detail_url = "https://e-propublico.pl" + details_href
                                    else:
                                        detail_url = details_href
                            org_column_text = (await cells[2].inner_text()).strip()
                            deadline_text = (await cells[3].inner_text()).strip().split("\n")
                            date_part = deadline_text[0].strip() if len(deadline_text) >= 1 else ""
                            time_part = deadline_text[1].strip() if len(deadline_text) >= 2 else ""
                            submission_deadline = DateStandardizer.standardize_deadline(f"{date_part} {time_part}".strip())
                            publication_dt = None
                            org_name = org_column_text
                            location = ""
                            if detail_url:
                                detail_info = await self.fetch_detail_info(context, detail_url)
                                publication_dt = detail_info.get("publication_dt")
                                detail_org = detail_info.get("org_name", "").strip()
                                if detail_org and detail_org != "Unknown":
                                    org_name = detail_org
                                location = detail_info.get("location", "")
                            if not publication_dt:
                                publication_dt = datetime.now()
                            if start_dt and publication_dt < start_dt:
                                logging.info(f"{self.source_type}: Skipping tender published at {publication_dt} < {start_dt}")
                                continue
                            else:
                                found_recent = True
                            init_date_str = publication_dt.strftime("%Y-%m-%d")
                            tender_data = {
                                "name": name,
                                "organization": org_name,
                                "location": location,
                                "submission_deadline": submission_deadline,
                                "initiation_date": init_date_str,
                                "details_url": detail_url,
                                "content_type": "tender",
                                "source_type": self.source_type,
                            }
                            t_obj = Tender(**tender_data)
                            tenders.append(t_obj)
                            logging.info(f"{self.source_type}: Extracted tender {signature} from {detail_url}")
                        except Exception as e:
                            logging.error(f"{self.source_type}: Error parsing row on page={current_page}: {str(e)}")
                            continue
                    await page.close()
                    if start_dt and not found_recent:
                        logging.info(f"{self.source_type}: No more recent tenders found on page={current_page}. Stopping early.")
                        break
                    current_page += 1
                return {
                    "tenders": tenders,
                    "metadata": ExtractorMetadata(total_tenders=len(tenders), pages_scraped=current_page - 1)
                }
        except Exception as e:
            logging.error(f"{self.source_type}: Critical error during extraction: {str(e)}")
            raise e
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    logging.error(f"{self.source_type}: Error closing browser: {str(e)}")

    async def find_updates(
        self,
        tenders_to_monitor: List[TenderAnalysisResult]
    ) -> Dict[str, List[Tuple[str, bytes, str, str]]]:
        """
        Checks if any new attachments have appeared for each TenderAnalysisResult in 'tenders_to_monitor'.
        Compares each attachment's date of publication (from the e-propublico detail page) with
        the tender's last updated_at (or created_at if updated_at is None).  If the attachment
        publication date is strictly greater, it is considered "new", and we download it.

        Returns:
            Dict[str, List[Tuple[str, bytes, str]]]
                A dict keyed by the string version of the tender's id, with a list of
                (filename, file_content, file_url) for each newly found attachment.
        """
        updates_found: Dict[str, List[Tuple[str, bytes, str, str]]] = {}
        if not tenders_to_monitor:
            return updates_found

        # We will create a single browser instance for all checks
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()

                for tender in tenders_to_monitor:
                    detail_url = tender.tender_url
                    if not detail_url:
                        continue

                    last_update_date = tender.updated_at or tender.created_at
                    if not last_update_date:
                        # fallback if something is off, skip
                        continue

                    # We will store newly found attachments in a list
                    new_attachments: List[Tuple[str, bytes, str]] = []
                    page = await context.new_page()
                    temp_dir = None
                    try:
                        await self._goto_with_retry(
                            page,
                            detail_url,
                            wait_until='networkidle',
                            timeout=15000,
                            retries=2,
                            purpose="find updates"
                        )

                        # Look for the "Dokumenty zamówienia" tab and click it
                        doc_tab_link = await page.query_selector("#navItem_dokumentyZamowienia")
                        if not doc_tab_link:
                            # No documents tab, no updates
                            await page.close()
                            continue

                        async with page.expect_navigation(timeout=15000):
                            await doc_tab_link.click()

                        await page.wait_for_selector("table#checkable tbody tr", timeout=15000)

                        # Prepare a temporary directory for downloads
                        temp_dir = Path(os.getcwd()) / "temp_downloads_updates"
                        temp_dir.mkdir(exist_ok=True)

                        # There can be multiple <table id="checkable"> elements on the page
                        tables = await page.query_selector_all("table#checkable")
                        # extraction_service = AssistantsFileExtractionService()
                        extraction_service = FileExtractionService()

                        for table in tables:
                            rows = await table.query_selector_all("tbody tr")
                            for row in rows:
                                try:
                                    # Parse the "Data publikacji" from the last column (or 4th index)
                                    cells = await row.query_selector_all("td")
                                    if len(cells) < 5:
                                        continue
                                    date_cell_text = (await cells[4].inner_text()).strip()
                                    if not date_cell_text:
                                        continue

                                    try:
                                        pub_date = datetime.strptime(date_cell_text, "%Y-%m-%d")
                                    except Exception:
                                        # If date parse fails, skip
                                        continue

                                    # Compare with the tender's last update date
                                    if pub_date.date() <= last_update_date.date():
                                        # Not newer -> skip
                                        continue

                                    # If we reached here, it's "newer", so download
                                    link = await row.query_selector("a[href*='/Dokumenty/Download/']")
                                    if not link:
                                        continue

                                    href = await link.get_attribute("href")
                                    if not href:
                                        continue

                                    download_url = "https://e-propublico.pl" + href

                                    async with page.expect_download(timeout=15000) as download_info:
                                        await link.click()
                                        download = await download_info.value

                                    suggested_name = download.suggested_filename or "document"
                                    temp_path = temp_dir / suggested_name

                                    await download.save_as(str(temp_path))

                                    # Process the file to get its (bytes, filename)
                                    file_results = await extraction_service.process_file_async(temp_path)
                                    for (file_content, filename, url, preview_chars, original_bytes) in file_results:
                                        new_attachments.append(
                                            (filename, file_content, url, preview_chars, original_bytes)
                                        )

                                except Exception as e:
                                    logging.error(f"{self.source_type}: Error checking row in {detail_url}: {str(e)}")
                                    continue

                        # If we found any new attachments, store them under this tender's ID
                        if new_attachments:
                            updates_found[str(tender.id)] = new_attachments

                    except Exception as e:
                        logging.error(f"{self.source_type}: Error while finding updates for {detail_url}: {str(e)}")

                    finally:
                        if temp_dir and temp_dir.exists():
                            shutil.rmtree(temp_dir, ignore_errors=True)
                        await page.close()

        except Exception as e:
            logging.error(f"{self.source_type}: Critical error in find_updates: {str(e)}")
            raise e
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    logging.error(f"{self.source_type}: Error closing browser: {str(e)}")

        return updates_found