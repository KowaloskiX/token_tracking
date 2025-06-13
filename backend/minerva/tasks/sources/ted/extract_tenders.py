import logging
import asyncio
from datetime import datetime
import os
from pathlib import Path
import random
import shutil
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from playwright.async_api import async_playwright

from minerva.core.database.database import db
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender


async def safe_goto(page, url, max_retries=2, initial_backoff=120, **kwargs):
    """
    Navigate to a URL. If a 429 error is encountered,
    wait and then retry (2 minutes, then 5 minutes).
    """
    backoff = initial_backoff
    for attempt in range(max_retries + 1):
        try:
            await page.goto(url, **kwargs)
            return  # success
        except Exception as e:
            if "429" in str(e):
                if attempt < max_retries:
                    logging.warning(
                        f"429 error when navigating to {url}. Waiting {backoff} seconds "
                        f"(attempt {attempt + 1}/{max_retries + 1})."
                    )
                    await asyncio.sleep(backoff)
                    backoff = 300  # next wait: 5 minutes
                else:
                    logging.error(
                        f"Failed to navigate to {url} after {max_retries + 1} attempts due to 429."
                    )
                    raise e
            else:
                raise e


class BaseTedCountryExtractor:
    """
    Base class for creating country-specific TED tender extractors.
    This allows for code reuse across different country extractors.
    """
    
    def __init__(self, country_code, priority_languages, source_type_name):
        """
        Initialize with country-specific parameters.
        
        Args:
            country_code: The country code used in the TED URL (e.g., "ITA" for Italy)
            priority_languages: List of languages to prioritize when downloading documents
            source_type_name: The source_type value to use in the tender data
        """
        self.country_code = country_code
        self.priority_languages = priority_languages
        self.source_type_name = source_type_name
        self.extraction_service = FileExtractionService()
        self.logger = logging.getLogger('minerva.services.tenders.tender_processor')

    async def extract_files_from_detail_page(self, context, details_url: str) -> List[Tuple[bytes, str, Optional[str], str]]:
        page = await context.new_page()
        processed_files = []
        temp_dir = None
        extraction_service = FileExtractionService()
        MAX_RETRIES = 3
        processed_languages = set()

        try:
            self.logger.info(f"Starting processing of detail page: {details_url}")
            unique_id = str(uuid4())
            temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
            temp_dir.mkdir(parents=True, exist_ok=True)
            retry_count = 0
            last_error = None
            success = False

            while retry_count < MAX_RETRIES and not success:
                try:
                    await page.wait_for_timeout(random.uniform(1000, 3000))
                    await safe_goto(page, details_url, wait_until='networkidle', timeout=30000)

                    try:
                        tender_id = await page.locator("div.notice-id").first.inner_text()
                        tender_id = tender_id.replace("/", "-").strip()
                    except Exception:
                        tender_id = "tender"

                    pdf_blocks = await page.query_selector_all("div.css-l0nske.e18vx3gy4")
                    if not pdf_blocks:
                        for selector in ["div[class*='pdf']", "div[class*='download']", "div.attachment"]:
                            pdf_blocks = await page.query_selector_all(selector)
                            if pdf_blocks:
                                self.logger.debug(f"Found blocks using alternative selector: {selector}")
                                break

                    self.logger.debug(f"Found {len(pdf_blocks)} PDF blocks")

                    for block in pdf_blocks:
                        try:
                            if len(processed_languages) >= 2:
                                break

                            lang_span = await block.query_selector("span")
                            link_elem = await block.query_selector("a.download-pdf")
                            if not link_elem:
                                for link_selector in ["a[href*='.pdf']", "a[class*='download']"]:
                                    link_elem = await block.query_selector(link_selector)
                                    if link_elem:
                                        break

                            if lang_span and link_elem:
                                lang_text = await lang_span.inner_text()
                                if lang_text in processed_languages:
                                    continue

                                # Use the country-specific priority languages
                                if lang_text in self.priority_languages:
                                    download_retry = 0
                                    while download_retry < 3:
                                        try:
                                            download_url = await link_elem.get_attribute("href")
                                            if download_url and download_url.startswith("/"):
                                                download_url = f"https://ted.europa.eu{download_url}"
                                            self.logger.debug(f"Attempting download from: {download_url}")

                                            async with page.expect_download(timeout=30000) as download_info:
                                                await link_elem.click()
                                                download = await download_info.value

                                                original_filename = download.suggested_filename or ""
                                                file_extension = Path(original_filename).suffix or ".pdf"
                                                file_name = f"{lang_text.lower()}_file{file_extension}"
                                                temp_path = temp_dir / file_name

                                                await download.save_as(temp_path)
                                                if temp_path.exists() and temp_path.stat().st_size > 0:
                                                    file_results = await extraction_service.process_file_async(temp_path)
                                                    for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results:
                                                        output_filename = filename
                                                        if output_filename.endswith('.txt'):
                                                            output_filename = f"{lang_text.lower()}_file.txt"
                                                        processed_files.append((file_content, output_filename, details_url, preview_chars, original_bytes))
                                                    processed_languages.add(lang_text)
                                                    self.logger.info(f"Successfully processed: {file_name}")
                                                    break
                                                else:
                                                    raise Exception("Downloaded file is empty or missing")
                                            await page.wait_for_timeout(1000)
                                            break
                                        except Exception as e:
                                            self.logger.warning(f"Download attempt {download_retry + 1} failed: {str(e)}")
                                            download_retry += 1
                                            if download_retry < 3:
                                                await page.wait_for_timeout(random.uniform(1000, 3000))
                                            else:
                                                self.logger.error("Failed all download attempts for file")
                        except Exception as e:
                            self.logger.error(f"Error processing PDF block: {str(e)}")
                            continue

                    if processed_files:
                        success = True
                    else:
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            self.logger.warning(f"No files processed, attempt {retry_count + 1} of {MAX_RETRIES}")
                            await page.wait_for_timeout(random.uniform(2000, 5000))
                        else:
                            self.logger.error("Failed to process any files after all retries")
                except Exception as e:
                    last_error = str(e)
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        self.logger.warning(f"Page processing failed, attempt {retry_count + 1} of {MAX_RETRIES}")
                        await page.wait_for_timeout(random.uniform(2000, 5000))
                    else:
                        self.logger.error(f"Failed to process page after all retries: {last_error}")

            self.logger.info(f"Successfully processed {len(processed_files)} files from {details_url}")
        except Exception as e:
            self.logger.error(f"Error accessing detail page {details_url}: {str(e)}")
        finally:
            try:
                await page.close()
                if temp_dir and temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                self.logger.error(f"Error during cleanup: {str(e)}")
        return processed_files

    async def get_organization_from_detail_page(self, context, detail_url: str) -> Tuple[str, str]:
        page = await context.new_page()
        organization = ""
        notice_type = ""
        try:
            await safe_goto(page, detail_url, wait_until='networkidle', timeout=20000)
            try:
                # First check for notice type in the summary section
                summary_section = page.locator("section#summary")
                if await summary_section.count() > 0:
                    first_div = summary_section.locator("div").first
                    if await first_div.count() > 0:
                        notice_type_span = first_div.locator("span[data-labels-key*='form-type']")
                        if await notice_type_span.count() > 0:
                            notice_type = await notice_type_span.inner_text()
                            logging.info(f"Found notice type: {notice_type}")

                # Then get the organization name
                official_name_labels = page.locator(
                    "span.label:has-text('Official name'), span.label:has-text('Official Name')"
                )
                if await official_name_labels.count() > 0:
                    label_elem = official_name_labels.nth(0)
                    parent = label_elem.locator("xpath=..")
                    data_elem = parent.locator("span.data")
                    if await data_elem.count() > 0:
                        organization = (await data_elem.inner_text()).strip()
            except Exception as e:
                logging.error(f"Error extracting official name or notice type: {e}")
                organization = ""
                notice_type = ""
        finally:
            await page.close()
        return organization, notice_type

    async def execute(self, inputs: Dict) -> Dict:
        max_pages = inputs.get("max_pages", 1)
        start_date_str = inputs.get("start_date")  # e.g., "2025-01-01"
        
        # Use the country-specific code in the URL
        listing_url = (
            "https://ted.europa.eu/en/search/result?"
            "search-scope=ACTIVE&scope=ACTIVE&onlyLatestVersions=false"
            f"&facet.place-of-performance=SPCY%2C{self.country_code}&sortColumn=publication-date&sortOrder=DESC"
            "&page=1&simpleSearchRef=true"
        )

        async with async_playwright() as p:
            logging.info(f"Launching headless browser for {self.country_code} TED scraping...")
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()

                logging.info(f"Navigating to {listing_url}")
                try:
                    await safe_goto(page, listing_url, wait_until='networkidle', timeout=30000)
                except Exception as e:
                    logging.error(f"Could not navigate to {listing_url}. Error: {e}")
                    return {
                        "tenders": [],
                        "metadata": ExtractorMetadata(total_tenders=0, pages_scraped=0)
                    }

                tenders = []
                current_page = 1
                found_older = False
                seen_urls = set()

                while current_page <= max_pages and not found_older:
                    logging.info(f"Scraping page {current_page}...")
                    try:
                        await page.wait_for_selector("table tbody tr", timeout=10000)
                        previous_count = 0
                        while True:
                            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                            await page.wait_for_timeout(2000)
                            current_count = await page.locator("table tbody tr").count()
                            if current_count == previous_count:
                                break
                            previous_count = current_count

                        rows = page.locator("table tbody tr")
                        row_count = await rows.count()
                        logging.info(f"Found {row_count} rows on page {current_page}.")

                        if row_count < 10:
                            logging.warning(
                                f"Row count ({row_count}) on page {current_page} is unexpectedly low. "
                                "Waiting 2 minutes and reloading page."
                            )
                            await asyncio.sleep(120)
                            await page.reload(wait_until='networkidle', timeout=30000)
                            await page.wait_for_selector("table tbody tr", timeout=15000)
                            rows = page.locator("table tbody tr")
                            row_count = await rows.count()
                            logging.info(f"After reload, found {row_count} rows on page {current_page}.")
                            if row_count < 10:
                                logging.error("Row count still too low after reload. Ending pagination.")
                                break

                        for row_index in range(row_count):
                            row = rows.nth(row_index)
                            cells = row.locator("td")
                            cell_count = await cells.count()
                            if cell_count < 6:
                                continue
                            try:
                                notice_num_cell = cells.nth(1)
                                notice_link = notice_num_cell.locator("a")
                                details_href = await notice_link.get_attribute("href")
                                detail_url = f"https://ted.europa.eu{details_href}"

                                if detail_url in seen_urls:
                                    logging.info(f"Skipping duplicate URL: {detail_url}")
                                    continue
                                seen_urls.add(detail_url)

                                description_cell = cells.nth(2)
                                name_span = description_cell.locator("span.css-u0hsu5.eeimd6y0").first
                                name = await name_span.inner_text()
                                if not name:
                                    name = await notice_link.inner_text()

                                publication_date_str = (await cells.nth(4).inner_text()).strip()
                                iso_initiation_date = ""
                                try:
                                    day, month, year_str = publication_date_str.split("/")
                                    iso_initiation_date = f"{year_str}-{month}-{day}"
                                except Exception:
                                    iso_initiation_date = publication_date_str

                                if start_date_str and iso_initiation_date:
                                    try:
                                        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                                        publication_dt = datetime.strptime(iso_initiation_date, "%Y-%m-%d")
                                        if publication_dt < start_dt:
                                            logging.info(
                                                f"Found older date {iso_initiation_date} "
                                                f"than start date {start_date_str}"
                                            )
                                            found_older = True
                                            break
                                    except ValueError as e:
                                        logging.error(f"Error parsing dates: {e}")

                                submission_deadline = ""
                                if cell_count > 5:
                                    submission_deadline_raw = (await cells.nth(5).inner_text()).strip()
                                    
                                    # First, remove any timezone information that might be in the raw string
                                    if '(' in submission_deadline_raw:
                                        submission_deadline_raw = submission_deadline_raw.split('(')[0].strip()
                                    
                                    try:
                                        # Try parsing the date with seconds if present
                                        if ':00' in submission_deadline_raw and submission_deadline_raw.count(':') > 1:
                                            dt = datetime.strptime(submission_deadline_raw, "%d/%m/%Y %H:%M:%S")
                                        else:
                                            # Standard format without seconds
                                            dt = datetime.strptime(submission_deadline_raw, "%d/%m/%Y %H:%M")
                                            
                                        # Format exactly as required
                                        submission_deadline = dt.strftime("%Y-%m-%d %H:%M")
                                    except ValueError as e:
                                        # If parsing fails, use a regex to extract just the date and time parts
                                        import re
                                        match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})', submission_deadline_raw)
                                        if match:
                                            try:
                                                extracted_date = match.group(1)
                                                dt = datetime.strptime(extracted_date, "%d/%m/%Y %H:%M")
                                                submission_deadline = dt.strftime("%Y-%m-%d %H:%M")
                                            except Exception:
                                                # Last resort: just remove anything after parentheses and keep as is
                                                submission_deadline = submission_deadline_raw
                                        else:
                                            submission_deadline = submission_deadline_raw

                                country = (await cells.nth(3).inner_text()).strip()
                                organization, notice_type = await self.get_organization_from_detail_page(context, detail_url)

                                # Skip if this is a result notice
                                if notice_type and "Result" in notice_type:
                                    logging.info(f"Skipping result notice at {detail_url}")
                                    continue

                                tender_data = {
                                    "name": name,
                                    "organization": organization or "Unknown from detail page",
                                    "location": country,
                                    "submission_deadline": submission_deadline,
                                    "initiation_date": iso_initiation_date,
                                    "details_url": detail_url,
                                    "content_type": "tender",
                                    "source_type": self.source_type_name
                                }

                                try:
                                    tender = Tender(**tender_data)
                                    tenders.append(tender)
                                    logging.debug(f"Added tender: {tender.name} ({tender.details_url})")
                                except Exception as e:
                                    logging.error(f"Error creating tender object: {e}")
                            except Exception as e:
                                logging.error(f"Error processing row {row_index} on page {current_page}: {e}")

                        if found_older:
                            logging.info("Found older date than start date, stopping pagination.")
                            break

                        if current_page >= max_pages:
                            logging.info(f"Reached maximum pages limit: {max_pages}")
                            break

                        next_buttons = page.locator("button[aria-label='Go to the next page']")
                        if await next_buttons.count() > 0:
                            next_button = next_buttons.first
                            logging.info(f"Found next page button on page {current_page}.")
                            await next_button.click()
                            await page.wait_for_timeout(3000)
                            await page.wait_for_selector("table tbody tr", timeout=15000)
                            current_page += 1
                        else:
                            logging.info("No next page button found, ending pagination.")
                            break

                    except Exception as e:
                        logging.error(f"Error processing page {current_page}: {e}")
                        break

                metadata = ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=current_page
                )
                logging.info(
                    f"{self.country_code} TED extraction complete. Extracted {len(tenders)} tenders from {current_page} pages."
                )
                logging.info(f"Total unique URLs processed: {len(seen_urls)}")

                return {
                    "tenders": tenders,
                    "metadata": metadata
                }
            finally:
                await context.close()
                await browser.close()

    async def find_updates(
        self,
        tenders_to_monitor: List[TenderAnalysisResult]
    ) -> Dict[str, List[Tuple[str, bytes, str, str]]]:
        """
        For each tender in `tenders_to_monitor`, this method will:
          1. Open the tender_url in a browser.
          2. Look for the alert indicating a new version ("Check out the latest version of this notice").
          3. If found, follow that link and use `extract_files_from_detail_page` to download any new files.
          4. If the alert states "This notice changes the previous version", skip it because
             it means we are already on the updated page.
          5. Return a dict mapping tender.id -> list of (filename, file_content, file_url) for newly extracted files.
        """

        updates_found: Dict[str, List[Tuple[str, bytes, str, str]]] = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            try:
                for tender in tenders_to_monitor:
                    # Initialize list of updates for this tender
                    updates_found[str(tender.id)] = []

                    url = tender.tender_url
                    if not url:
                        continue

                    self.logger.info(f"Checking updates for tender: {tender.id} at {url}")
                    page = await context.new_page()

                    # Go to the tender_url
                    try:
                        await safe_goto(page, url, wait_until='networkidle', timeout=30000)
                    except Exception as e:
                        self.logger.error(f"Could not navigate to {url}: {e}")
                        await page.close()
                        continue

                    # Locate any alert boxes on the page
                    alert_boxes = page.locator("div.CustomReactClasses-MuiAlert-root")

                    if await alert_boxes.count() > 0:
                        # Check each alert box
                        for i in range(await alert_boxes.count()):
                            alert_text = await alert_boxes.nth(i).inner_text()

                            # Case 1: "Check out the latest version..." => Follow the link
                            if "Check out the latest version of this notice" or "Submission deadline has been amended by" in alert_text:
                                # Find the <a> inside this alert
                                new_version_link = alert_boxes.nth(i).locator("a")
                                if await new_version_link.count() > 0:
                                    link_href = await new_version_link.first.get_attribute("href")
                                    if link_href and link_href.startswith("/"):
                                        new_version_url = f"https://ted.europa.eu{link_href}"
                                        self.logger.info(
                                            f"New version detected for tender {tender.id}, URL: {new_version_url}"
                                        )
                                        # insert new url to db
                                        db["tender_analysis_results"].update_one(
                                            {"_id": tender.id},
                                            {
                                                "$set": {
                                                    "tender_url": new_version_url
                                                }
                                            }
                                        )
                                        # Extract new files from the new version page
                                        try:
                                            extracted_files = await self.extract_files_from_detail_page(
                                                context, new_version_url
                                            )
                                            updates_found[str(tender.id)] = [
                                                (filename, file_content, file_url, preview_chars, original_bytes)
                                                for (file_content, filename, file_url, preview_chars, original_bytes)
                                                in extracted_files
                                            ]
                                        except Exception as ex:
                                            self.logger.error(
                                                f"Error extracting files for new version of "
                                                f"tender {tender.id}: {str(ex)}"
                                            )
                                # If we found a valid "new version" link, we can stop checking further alerts
                                break

                            # Case 2: "This notice changes the previous version" => Already the newest version
                            elif "This notice changes the previous version" in alert_text:
                                self.logger.info(
                                    f"Tender {tender.id} is already the latest version; no further action."
                                )
                                # We do not want to process it as an update, so break
                                break

                    else:
                        self.logger.info(f"No alerts found for tender {tender.id}.")

                    # Close the page before moving to the next tender
                    await page.close()

            finally:
                await context.close()
                await browser.close()

        return updates_found