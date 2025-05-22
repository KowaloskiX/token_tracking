import logging
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from playwright.async_api import async_playwright
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender


class OrlenConnectTenderExtractor:
    """
    An extractor for the Orlen Connect main page:
    https://connect.orlen.pl/servlet/HomeServlet?mp_module=main&mp_action=mainPage

    This extractor:
      - Clicks the "Pokaż więcej" button repeatedly to load additional tenders.
      - For each tender, navigates to its details page to extract the tender start date ("Rozpoczęcie składania ofert")
        and the submission deadline ("Zakończenie składania ofert").
      - If a tender's start date is older than the provided start_date, it stops scraping further.
    """

    def __init__(self, source_type: str = "orlenconnect"):
        self.base_list_url = "https://connect.orlen.pl/servlet/HomeServlet?mp_module=main&mp_action=mainPage"
        self.source_type = source_type

    async def _goto_with_retry(self, page, url: str, wait_until: str, timeout: int, retries: int = 2, purpose: str = "navigation"):
        for attempt in range(retries + 1):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return
            except Exception as e:
                if attempt < retries:
                    logging.info(f"{self.source_type}: Retrying to load URL: {url} (attempt {attempt+1}) for {purpose}")
                else:
                    logging.error(f"{self.source_type}: Timeout/error loading URL: {url} for {purpose}")
                    raise e

    async def fetch_tender_dates(self, context, details_url: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Navigate to the tender detail page and extract:
        - tender_start: Date from "Rozpoczęcie składania ofert"
        - submission_deadline: Date from "Zakończenie składania ofert"
        Returns a tuple (tender_start, submission_deadline) as datetime objects, or None if not found.
        """
        page = await context.new_page()
        tender_start = None
        submission_deadline = None
        try:
            await self._goto_with_retry(
                page, details_url, wait_until='networkidle', timeout=15000, retries=2, purpose="tender details"
            )
            # Locate the aside element that contains the inquiry summary.
            aside = await page.query_selector("aside#inquiry-summary")
            if aside:
                # Assume the first section within the aside contains the dates.
                section = await aside.query_selector("section")
                if section:
                    # Find all <h3> elements in this section.
                    h3_elements = await section.query_selector_all("h3")
                    for h3 in h3_elements:
                        h3_text = (await h3.inner_text()).strip()
                        # Use evaluate_handle to get the next sibling <p> element.
                        p_handle = await h3.evaluate_handle("node => node.nextElementSibling")
                        if p_handle:
                            date_text = (await p_handle.inner_text()).strip()
                            parsed_date = None
                            # Try a few common date formats.
                            for fmt in ("%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M"):
                                try:
                                    parsed_date = datetime.strptime(date_text, fmt)
                                    break
                                except ValueError:
                                    continue
                            if parsed_date:
                                if "Rozpoczęcie składania ofert" in h3_text:
                                    tender_start = parsed_date
                                elif "Zakończenie składania ofert" in h3_text:
                                    submission_deadline = parsed_date
                else:
                    logging.error(f"{self.source_type}: No <section> found in inquiry summary at {details_url}.")
            else:
                logging.error(f"{self.source_type}: Inquiry summary aside not found in details page {details_url}.")
        except Exception as e:
            logging.error(f"{self.source_type}: Error extracting tender dates from {details_url}: {str(e)}")
        finally:
            await page.close()
        return tender_start, submission_deadline


    async def extract_files_from_detail_page(self, context, details_url: str) -> List[Tuple[bytes, str, str, Optional[str]]]:
        page = await context.new_page()
        processed_files = []
        extraction_service = FileExtractionService()
        temp_dir = None
        try:
            await self._goto_with_retry(page, details_url, wait_until='networkidle', timeout=15000, retries=2, purpose="extract files")
            attachments_section = await page.query_selector("section.attachments")
            if not attachments_section:
                logging.info(f"{self.source_type}: No attachments section found at {details_url}.")
                return processed_files

            file_rows = await attachments_section.query_selector_all("ul.docs-list li.item")
            if not file_rows:
                logging.info(f"{self.source_type}: No document rows found at {details_url}.")
                return processed_files

            unique_id = str(uuid4())
            temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
            temp_dir.mkdir(parents=True, exist_ok=True)

            for row in file_rows:
                try:
                    link = await row.query_selector("a")
                    if not link:
                        continue
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    download_url = href if href.startswith("http") else "https://connect.orlen.pl" + href
                    async with page.expect_download(timeout=15000) as download_info:
                        await link.click()
                        download = await download_info.value
                    suggested_name = download.suggested_filename or "document"
                    temp_path = temp_dir / suggested_name
                    await download.save_as(str(temp_path))
                    file_results = await extraction_service.process_file_async(temp_path)
                    for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results:
                        processed_files.append((file_content, filename, download_url, preview_chars, original_bytes))
                    logging.info(f"Downloaded and processed {suggested_name}")
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

        For Orlen Connect:
          - The main page loads tenders dynamically.
          - Each click on the "Pokaż więcej" button is treated as the next page (up to max_pages clicks).
          - After processing currently loaded tender elements, if the page bottom is reached and the tender start dates
            are still newer than the provided start_date, the scraper clicks "Pokaż więcej" to load additional tenders.
          - If a tender's "Rozpoczęcie składania ofert" is older than the provided start_date, scraping stops.
        """
        start_date_str = inputs.get("start_date", None)
        max_pages = inputs.get("max_pages", 10)
        start_dt = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                logging.info(f"{self.source_type}: Starting extraction with start_date: {start_date_str}")
            except ValueError:
                logging.error(f"{self.source_type}: Invalid date format for start_date: {start_date_str}")
        else:
            logging.info(f"{self.source_type}: Starting extraction with no start_date.")

        browser = None
        tenders = []
        processed_count = 0
        current_page = 1
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                logging.info(f"{self.source_type}: Navigating to main page: {self.base_list_url}")
                await self._goto_with_retry(page, self.base_list_url, wait_until='networkidle', timeout=15000, retries=2, purpose="main page")

                # Main loop: process currently loaded tender elements and click "Pokaż więcej" when needed.
                while True:
                    # Allow time for dynamic content to settle.
                    await page.wait_for_timeout(2000)
                    tender_elements = await page.query_selector_all("section.demand-item")
                    total_elements = len(tender_elements)
                    logging.info(f"{self.source_type}: Found {total_elements} tenders so far on page {current_page}.")

                    if total_elements <= processed_count:
                        logging.info(f"{self.source_type}: No new tender elements found, ending scraping.")
                        break

                    # Process new tender elements only.
                    for elem in tender_elements[processed_count:]:
                        try:
                            name_link = await elem.query_selector("a.demand-item-details-name")
                            if not name_link:
                                continue
                            details_href = await name_link.get_attribute("href")
                            if not details_href:
                                continue
                            detail_url = details_href if details_href.startswith("http") else "https://connect.orlen.pl" + details_href
                            tender_name = (await name_link.inner_text()).strip()
                            number_elem = await elem.query_selector("b.demand-item-details-number")
                            tender_number = (await number_elem.inner_text()).strip() if number_elem else ""
                            org_elem = await elem.query_selector("span[data-bind*='org.name']")
                            organization = (await org_elem.inner_text()).strip() if org_elem else "Unknown"

                            # Fetch tender start and submission deadline from the detail page.
                            tender_start_date, tender_submission_deadline = await self.fetch_tender_dates(context, detail_url)
                            
                            # If tender start date is available and is older than the provided start_date, stop scraping.
                            if start_dt and tender_start_date and tender_start_date < start_dt:
                                logging.info(f"{self.source_type}: Tender {tender_number} with start date {tender_start_date} is older than {start_dt}. Ending scraping.")
                                raise StopIteration

                            # Use current datetime as fallback if dates are not found.
                            tender_start_date = tender_start_date or datetime.now()
                            tender_submission_deadline = tender_submission_deadline or datetime.now()

                            tender_data = {
                                "name": tender_name,
                                "organization": organization,
                                "location": "",  # Additional detail extraction can be added if needed.
                                "submission_deadline": tender_submission_deadline.strftime("%Y-%m-%d"),
                                "initiation_date": tender_start_date.strftime("%Y-%m-%d"),
                                "details_url": detail_url,
                                "content_type": "tender",
                                "source_type": self.source_type,
                            }
                            t_obj = Tender(**tender_data)
                            tenders.append(t_obj)
                            logging.info(f"{self.source_type}: Extracted tender {tender_number} - {tender_name}")
                        except StopIteration:
                            raise
                        except Exception as e:
                            logging.error(f"{self.source_type}: Error parsing a tender element: {str(e)}")
                            continue

                    processed_count = total_elements

                    # Check if we've reached the maximum number of pages.
                    if current_page >= max_pages:
                        logging.info(f"{self.source_type}: Reached maximum pages limit ({max_pages}).")
                        break

                    # Click the "Pokaż więcej" button if available.
                    load_more_button = await page.query_selector("a.link-btn.link-load-more")
                    if load_more_button:
                        try:
                            async with page.expect_response(lambda response: response.status == 200, timeout=15000):
                                await load_more_button.click()
                            current_page += 1
                            logging.info(f"{self.source_type}: Clicked 'Pokaż więcej' for page {current_page}.")
                        except Exception as e:
                            logging.info(f"{self.source_type}: No more tenders loaded after clicking 'Pokaż więcej': {str(e)}")
                            break
                    else:
                        logging.info(f"{self.source_type}: 'Pokaż więcej' button not found, ending scraping.")
                        break

                await page.close()
                metadata = ExtractorMetadata(total_tenders=len(tenders), pages_scraped=current_page)
                return {"tenders": tenders, "metadata": metadata}
        except StopIteration:
            logging.info(f"{self.source_type}: Stopping scraping due to tender start date condition.")
            metadata = ExtractorMetadata(total_tenders=len(tenders), pages_scraped=current_page)
            return {"tenders": tenders, "metadata": metadata}
        except Exception as e:
            logging.error(f"{self.source_type}: Critical error during extraction: {str(e)}")
            raise e
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    logging.error(f"{self.source_type}: Error closing browser: {str(e)}")
