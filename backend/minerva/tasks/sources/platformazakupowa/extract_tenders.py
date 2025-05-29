import logging
from datetime import datetime
import os
from pathlib import Path
import random
import shutil
import tempfile
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
from bs4 import BeautifulSoup
import urllib.parse
from minerva.core.services.vectorstore.file_content_extract.base import ExtractorRegistry
# Import helper functions for BZP
from minerva.tasks.sources.helpers import extract_bzp_plan_fields, scrape_bzp_budget_row

from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from playwright.async_api import async_playwright
from minerva.core.utils.date_standardizer import DateStandardizer
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender


class PlatformaZakupowaTenderExtractor:
    def __init__(self):
        self.base_url = "https://platformazakupowa.pl"
        self.list_url = (
            "https://platformazakupowa.pl/all"
            "?page={page}"
            "&pageEnded=1"
            "&limit=30"
            "&limitEnded=30"
            "&query="
            "&searchIn=1,2,7,3,4,6"
            "&globalMode=all"
            "&proceedingType=all"
            "&negotiationStatus=128,256,512,33554432"
            "&tab=active"
            "&year=one_day"
        )
        self.source_type = "platformazakupowa"

    async def fetch_detail_info(self, context, detail_url: str) -> dict:
        """Fetch additional information from tender detail page"""
        page = await context.new_page()
        detail_info = {
            "description": "",
            "location": "",
            "requirements": "",
            "evaluation_criteria": "",
            "org_name": "",
            "initiation_date": None,
            "submission_deadline_detail": None
        }
        
        try:
            await page.goto(detail_url, wait_until='networkidle', timeout=15000)
            
            # Get basic info
            soup = BeautifulSoup(await page.content(), 'html.parser')

            # Get organization info from header
            org_div = soup.select_one("div.proceeding-info-list-item")
            if org_div:
                detail_info["org_name"] = (
                    org_div.get_text(strip=True)
                    .replace("Organizacja", "")
                    .strip()
                )

            # Get publication date
            pub_date_div = soup.select_one(
                "div.proceeding-info-list-item:-soup-contains('Zamieszczenia')"
            )
            if pub_date_div:
                date_text = pub_date_div.select_one("span.proceeding-info-date")
                if date_text:
                    detail_info["initiation_date"] = date_text.get_text(strip=True)

            # Get submission deadline from detail page
            deadline_li = soup.select_one("li.proceeding-info-list-item:-soup-contains('Składania')")
            if deadline_li:
                date_span = deadline_li.select_one("span.proceeding-info-date")
                time_span = deadline_li.select_one("span.proceeding-info-time")
                date_text = date_span.get_text(strip=True) if date_span else None
                time_text = time_span.get_text(strip=True) if time_span else None
                
                if date_text and time_text:
                    # Combine date and HH:MM part of time
                    detail_info["submission_deadline_detail"] = f"{date_text} {time_text[:5]}"
                elif date_text: # If only date is present
                    detail_info["submission_deadline_detail"] = f"{date_text} 00:00" # Default time

            # Get description/requirements from main content
            requirements_div = soup.select_one("div#requirements")
            if requirements_div:
                detail_info["description"] = requirements_div.get_text(strip=True)

            # Get location if available
            location_div = soup.select_one("div.proceeding-info-list-item:-soup-contains('Location')")
            if location_div:
                detail_info["location"] = location_div.get_text(strip=True)

        except Exception as e:
            logging.error(f"Error fetching detail info from {detail_url}: {str(e)}")
        finally:
            await page.close()
        
        return detail_info

    async def extract_files_from_detail_page(
        self,
        context,
        details_url: str
    ) -> List[Tuple[bytes, str, Optional[str]]]:
        """Extract files from tender detail page"""
        page = await context.new_page()
        processed_files = []
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        temp_dir = None
        MAX_RETRIES = 3
        
        try:
            # Create temp directory using tempfile for better reliability
            unique_id = str(uuid4())
            temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            retry_count = 0
            success = False
            
            # Use a specific context for BZP scraping later if needed
            async with async_playwright() as p_bzp:

                while retry_count < MAX_RETRIES and not success:
                    try:
                        # Add random delay to avoid rate limiting
                        await page.wait_for_timeout(random.uniform(1000, 3000))
                        
                        # Navigate to page with increased timeout
                        await page.goto(details_url, wait_until='networkidle', timeout=30000)
                        
                        # Close the chatbot widget if present
                        try:
                            close_button = await page.query_selector('button.on-widget-close-button')
                            if close_button:
                                await close_button.click()
                                await page.wait_for_timeout(1000)  # Wait for close animation
                        except Exception as e:
                            logging.debug(f"No chatbot close button found or error clicking it: {e}")
                        
                        # Extract tender ID for filenames
                        tender_id = details_url.split('/')[-1]
                        
                        # First extract requirements and evaluation criteria
                        soup = BeautifulSoup(await page.content(), 'html.parser')
                        
                        # Create content for tender details text file
                        details_content = []
                        
                        # Extract requirements
                        requirements_div = soup.select_one("div#requirements")
                        if requirements_div:
                            details_content.append("=== REQUIREMENTS ===")
                            details_content.append(requirements_div.get_text(strip=True))
                            details_content.append("\n")
                        
                        # Extract evaluation criteria
                        criteria_div = soup.select_one("div.col-md-12.requirements")
                        if criteria_div:
                            details_content.append("=== EVALUATION CRITERIA ===")
                            details_content.append(criteria_div.get_text(strip=True))
                        
                        # Save tender details as text file
                        if details_content:
                            details_filename = f"tender_{tender_id}_details.txt"
                            details_text = "\n\n".join(details_content)
                            details_bytes = details_text.encode('utf-8')
                            processed_files.append(
                                (details_bytes, details_filename, details_url, details_text[:250], details_bytes)
                            )

                        # Get file information using JavaScript evaluation
                        file_data = await page.evaluate('''() => {
                            const files = [];
                            document.querySelectorAll('#allAttachmentsTable tbody tr').forEach(row => {
                                const nameCell = row.querySelector('td:first-child');
                                const downloadLink = row.querySelector('a.proceeding-file-download');
                                if (nameCell && downloadLink) {
                                    let filename = nameCell.textContent.trim();
                                    // Remove icon text if present
                                    filename = filename.replace(/^[^a-zA-Z0-9]*/, '').trim();
                                    files.push({
                                        filename: filename,
                                        downloadUrl: downloadLink.href
                                    });
                                }
                            });
                            return files;
                        }''')

                        if not file_data:
                            logging.warning(f"No file data found on attempt {retry_count + 1}")
                            retry_count += 1
                            continue

                        for file_info in file_data:
                            download_retry = 0
                            while download_retry < 3:  # Retry individual downloads up to 3 times
                                try:
                                    filename = file_info['filename']
                                    download_url = file_info['downloadUrl']
                                    
                                    if download_url.startswith('//'):
                                        download_url = f'https:{download_url}'
                                    
                                    # Try to find the download link element
                                    download_links = await page.query_selector_all('a.proceeding-file-download')
                                    download_link = None
                                    
                                    for link in download_links:
                                        href = await link.get_attribute('href')
                                        if href and (href == download_url or f'https:{href}' == download_url):
                                            download_link = link
                                            break
                                    
                                    if not download_link:
                                        logging.error(f"Download link not found for {filename}")
                                        break

                                    # Ensure the download link is visible and not covered
                                    await download_link.scroll_into_view_if_needed()
                                    # Close the chatbot widget again, in case it reappeared
                                    try:
                                        close_button = await page.query_selector('button.on-widget-close-button')
                                        if close_button:
                                            await close_button.click()
                                            await page.wait_for_timeout(500)  # Brief wait for close
                                    except Exception as e:
                                        logging.debug(f"No chatbot close button found: {e}")
                                    
                                    # Setup download handling with timeout
                                    async with page.expect_download(timeout=30000) as download_info:
                                        await download_link.click()
                                        download = await download_info.value
                                        
                                        # Generate unique temp path
                                        temp_path = temp_dir / f"{filename}"
                                        
                                        # Save download directly to temp path
                                        await download.save_as(temp_path)
                                        
                                        if temp_path.exists() and temp_path.stat().st_size > 0:
                                            # Process the file using async wrapper
                                            file_results = await extraction_service.process_file_async(temp_path)
                                            for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results:
                                                processed_files.append(
                                                    (file_content, filename, download_url, preview_chars, original_bytes)
                                                )
                                            
                                            logging.info(f"Successfully downloaded and processed: {filename}")
                                            break  # Success, exit retry loop
                                        else:
                                            raise Exception("Downloaded file is empty or missing")

                                    # Add delay between downloads
                                    await page.wait_for_timeout(random.uniform(1000, 2000))

                                except Exception as e:
                                    logging.error(f"Download attempt {download_retry + 1} failed for {filename}: {str(e)}")
                                    download_retry += 1
                                    if download_retry < 3:
                                        await page.wait_for_timeout(random.uniform(2000, 4000))

                        if processed_files:
                            success = True
                            logging.info(f"Successfully processed {len(processed_files)} files")
                        else:
                            retry_count += 1
                            if retry_count < MAX_RETRIES:
                                logging.warning(f"No files processed, attempt {retry_count + 1} of {MAX_RETRIES}")
                                await page.wait_for_timeout(random.uniform(2000, 5000))
                            else:
                                logging.error("Failed to process any files after all retries")

                    except Exception as e:
                        logging.error(f"Error during page processing attempt {retry_count + 1}: {str(e)}")
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            await page.wait_for_timeout(random.uniform(2000, 5000))

            # === Start BZP Budget Extraction Logic ===
            plan_num, plan_id = None, None
            pdf_extractor = ExtractorRegistry().get('.pdf')
            for content, out_name, url, preview, original_bytes in processed_files:
                try:
                    if out_name.lower().endswith(".pdf"):
                        temp_pdf_path = temp_dir / out_name
                        if temp_pdf_path.exists() and pdf_extractor:
                            text = pdf_extractor.extract_text_as_string(temp_pdf_path)
                            bzp_num, bzp_id = extract_bzp_plan_fields(text)
                            if bzp_num and bzp_id:
                                plan_num, plan_id = bzp_num, bzp_id
                                logging.info(f"{self.source_type}: Found BZP details in {out_name}: Plan={plan_num}, ID={plan_id}")
                                break
                except Exception as e:
                    logging.warning(f"{self.source_type}: Error decoding/searching {out_name} for BZP fields: {e}")

            if plan_num and plan_id:
                plan_short_id = plan_id.split()[0] if plan_id else plan_id
                logging.info(f"{self.source_type}: Attempting to scrape BZP budget for Plan={plan_num}, PosID={plan_short_id}")
                try:
                    budget_row_data = await scrape_bzp_budget_row(context, plan_num, plan_short_id)
                    if budget_row_data:
                        row_str, bzp_url = budget_row_data
                        budget_info = (
                            f"**Dane z planu postępowań BZP**\n"
                            f"Przewidywany budżet/Orientacyjna wartość/cena zamówienia:\n{row_str}\n"
                        )
                        logging.info(f"{self.source_type}: Successfully scraped BZP budget row.")
                    else:
                        budget_info = (
                            f"---\n"
                            f"Nie znaleziono pozycji {plan_short_id} w planie {plan_num} na BZP.\n"
                            f"URL sprawdzony: https://ezamowienia.gov.pl/mo-client-board/bzp/tender-details/{urllib.parse.quote(plan_num, safe='')}\n"
                        )
                        logging.warning(f"{self.source_type}: BZP budget row not found for Plan={plan_num}, PosID={plan_short_id}")

                    processed_files.append((
                        budget_info.encode("utf-8"),
                        "bzp_budget.txt",
                        None,  # No direct URL for this derived file
                        budget_info[:200],
                        budget_info.encode("utf-8")
                    ))
                except Exception as e:
                    logging.error(f"{self.source_type}: Error during BZP budget scraping: {e}")
                    processed_files.append((
                    f"Error scraping BZP budget: {e}".encode("utf-8"),
                    "bzp_budget_error.txt",
                     None,
                    f"Error scraping BZP budget: {e}"[:200],
                    None
                    ))

        except Exception as e:
            logging.error(f"Error accessing detail page {details_url}: {str(e)}")
        finally:
            try:
                await page.close()
                if temp_dir and temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logging.error(f"Error during cleanup: {str(e)}")

        return processed_files

    async def execute(self, inputs: Dict) -> Dict:
        """Main execution method to scrape tenders"""
        max_pages = inputs.get('max_pages', 70)
        start_date = inputs.get('start_date', None)
        
        start_dt = None
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                logging.info(f"Starting extraction with start_date: {start_date}")
            except ValueError:
                logging.error(f"Invalid date format for start_date: {start_date}")
        else:
            logging.info("Starting extraction with no start_date.")

        # Use a try/finally around the entire browser usage
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()

                tenders = []
                current_page = 1

                while current_page <= max_pages:
                    try:
                        url = self.list_url.format(page=current_page)
                        logging.info(f"Processing page {current_page}")
                        await page.goto(url, wait_until='networkidle', timeout=15000)

                        # Wait for tender listings to load
                        await page.wait_for_selector("div.auction-row", timeout=10000)

                        # Get tender rows
                        tender_rows = await page.query_selector_all("div.auction-row")
                        if not tender_rows:
                            logging.info("No more tenders found")
                            break

                        for row in tender_rows:
                            try:
                                # Get tender link and title
                                title_link = await row.query_selector("a.auction-title")
                                if not title_link:
                                    continue

                                name = await title_link.inner_text()
                                name = name.strip()
                                
                                detail_url = await title_link.get_attribute("href")
                                if detail_url:
                                    if not detail_url.startswith("http"):
                                        detail_url = f"{self.base_url}{detail_url}"
                                else:
                                    continue

                                # Get organization
                                org_div = await row.query_selector("div.product-info")
                                organization = "Unknown"
                                if org_div:
                                    org_text = await org_div.inner_text()
                                    # Split by newlines and take second line which contains org name
                                    org_lines = org_text.split("\n")
                                    if len(org_lines) > 1:
                                        organization = org_lines[1].strip()

                                # Get details from tender page FIRST to check for deadline
                                detail_info = await self.fetch_detail_info(context, detail_url)

                                # Use deadline from detail page if available (YYYY-MM-DD format)
                                submission_deadline = detail_info.get("submission_deadline_detail", None)
                                logging.info(f'[Tender: {name[:30]}...] Deadline from detail page: {submission_deadline}')
                                
                                # If not found on detail page, parse from list page (fallback)
                                if not submission_deadline:
                                    logging.info(f'[Tender: {name[:30]}...] Deadline not found on detail page, using list page fallback.')
                                    deadline_elem = await row.query_selector("span.auction-time b")
                                    if deadline_elem:
                                        deadline_text = await deadline_elem.inner_text()
                                        deadline_text = deadline_text.strip()
                                        logging.info(f'[Tender: {name[:30]}...] Fallback deadline text from list page: "{deadline_text}"')
                                        
                                        try:
                                            # First, try parsing as YYYY-MM-DD HH:MM:SS or YYYY-MM-DD HH:MM or YYYY-MM-DD
                                            dt = None
                                            try:
                                                if len(deadline_text.split()) > 1 and len(deadline_text.split()[1].split(':')) == 3: # YYYY-MM-DD HH:MM:SS
                                                    dt = datetime.strptime(deadline_text, "%Y-%m-%d %H:%M:%S")
                                                elif len(deadline_text.split()) > 1 and len(deadline_text.split()[1].split(':')) == 2: # YYYY-MM-DD HH:MM
                                                    dt = datetime.strptime(deadline_text, "%Y-%m-%d %H:%M")
                                                else: # Just YYYY-MM-DD
                                                    dt = datetime.strptime(deadline_text.split()[0], "%Y-%m-%d")
                                                submission_deadline = dt.strftime("%Y-%m-%d %H:%M")
                                                logging.info(f'[Tender: {name[:30]}...] Parsed list fallback deadline (YYYY-MM-DD format): {submission_deadline}')
                                            except ValueError:
                                                # If YYYY-MM-DD fails, try DD-MM-YYYY HH:MM:SS or DD-MM-YYYY HH:MM or DD-MM-YYYY
                                                dt = None
                                                try:
                                                    if len(deadline_text.split()) > 1 and len(deadline_text.split()[1].split(':')) == 3: # DD-MM-YYYY HH:MM:SS
                                                        dt = datetime.strptime(deadline_text, "%d-%m-%Y %H:%M:%S")
                                                    elif len(deadline_text.split()) > 1 and len(deadline_text.split()[1].split(':')) == 2: # DD-MM-YYYY HH:MM
                                                        dt = datetime.strptime(deadline_text, "%d-%m-%Y %H:%M")
                                                    else: # Just DD-MM-YYYY
                                                         dt = datetime.strptime(deadline_text.split()[0], "%d-%m-%Y")
                                                    submission_deadline = dt.strftime("%Y-%m-%d %H:%M") # Convert to desired format
                                                    logging.info(f'[Tender: {name[:30]}...] Parsed list fallback deadline (DD-MM-YYYY format) and converted: {submission_deadline}')
                                                except ValueError:
                                                    # If both formats fail
                                                    logging.warning(f"Could not parse deadline date/time from list page '{deadline_text}' using YYYY-MM-DD or DD-MM-YYYY formats with time.")
                                                    submission_deadline = ""
                                                    
                                        except Exception as e:
                                            # Catch any other unexpected errors during processing
                                            logging.error(f"Unexpected error processing fallback deadline '{deadline_text}': {e}")
                                            submission_deadline = ""
                                
                                # If still no deadline, set to empty string
                                if not submission_deadline:
                                    submission_deadline = ""
                                logging.info(f'[Tender: {name[:30]}...] Final submission deadline: "{submission_deadline}"')

                                # Check publication date against start_date if provided
                                if start_dt and detail_info.get("initiation_date"):
                                    pub_dt = datetime.strptime(detail_info["initiation_date"], "%Y-%m-%d")
                                    if pub_dt < start_dt:
                                        logging.info(f"Skipping tender published at {pub_dt} (before {start_dt})")
                                        continue

                                # Create tender object
                                tender_data = {
                                    "name": name,
                                    "organization": detail_info.get("org_name") or organization,
                                    "location": detail_info.get("location", ""),
                                    "submission_deadline": submission_deadline,
                                    "initiation_date": detail_info.get("initiation_date") or datetime.now().strftime("%Y-%m-%d"),
                                    "details_url": detail_url,
                                    "content_type": "tender",
                                    "source_type": "platformazakupowa",
                                }

                                try:
                                    tender = Tender(**tender_data)
                                    tenders.append(tender)
                                    logging.info(f"Added tender: {tender.name}")
                                except Exception as e:
                                    logging.error(f"Error creating Tender object: {str(e)}")
                                    continue

                            except Exception as e:
                                logging.error(f"Error processing tender row: {str(e)}")
                                continue

                        # Check for next page
                        next_pagination = await page.query_selector("li.active + li a")
                        if not next_pagination:
                            logging.info("No more pages available")
                            break

                        current_page += 1

                    except Exception as e:
                        logging.error(f"Error processing page {current_page}: {str(e)}")
                        break

                # Build the metadata and final result
                metadata = ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=current_page
                )

                logging.info(f"Extraction complete. Found {len(tenders)} tenders.")
                return {
                    "tenders": tenders,
                    "metadata": metadata
                }

            finally:
                # Ensure context and browser are closed in all cases
                await context.close()
                await browser.close()

    async def extract_announcement_files(
        self,
        page,
        attachment_links: List[str]
    ) -> List[Tuple[bytes, str, str]]:
        """
        Download and extract the given list of announcement attachment links.
        Returns a list of (file_content, filename, file_url).
        """
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        processed_files = []
        temp_dir = None

        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="announcement_downloads_"))
            
            # Close the chatbot widget if present
            try:
                close_button = await page.query_selector('button.on-widget-close-button')
                if close_button:
                    await close_button.click()
                    await page.wait_for_timeout(1000)  # Wait for close animation
            except Exception as e:
                logging.debug(f"No chatbot close button found or error clicking it: {e}")
            
            for link_url in attachment_links:
                # filename = link_url.split("/")[-1] or f"attachment_{random.randint(1000,9999)}"
                
                # Ensure full https URL if it starts with //
                if link_url.startswith('//'):
                    link_url = f'https:{link_url}'
                
                # Attempt to locate the link element on the page
                link_elements = await page.query_selector_all("a")
                link_element = None
                for elem in link_elements:
                    href = await elem.get_attribute('href')
                    if href and (href == link_url or f"https:{href}" == link_url or f"//platformazakupowa.pl{href}" == link_url):
                        link_element = elem
                        break
                
                if not link_element:
                    # If we cannot match exactly, skip or log error
                    logging.error(f"Could not find matching link element for {link_url}")
                    continue

                link_text = await link_element.inner_text()
                url_filename = link_url.split("/")[-1] or f"attachment_{random.randint(1000,9999)}"
                prefix = link_text.split("[")[0].strip()
                if prefix:
                    # sanitize a bit
                    prefix = prefix.replace('/', '_').replace('\\', '_')
                    filename = f"{prefix} {url_filename}"
                else:
                    filename = url_filename
                # Perform the download
                try:
                    # Ensure the link is visible and not covered
                    await link_element.scroll_into_view_if_needed()
                    # Close the chatbot widget again, in case it reappeared
                    try:
                        close_button = await page.query_selector('button.on-widget-close-button')
                        if close_button:
                            await close_button.click()
                            await page.wait_for_timeout(500)  # Brief wait for close
                    except Exception as e:
                        logging.debug(f"No chatbot close button found: {e}")
                    
                    async with page.expect_download(timeout=30000) as download_info:
                        await link_element.click()
                        download = await download_info.value
                        
                        temp_path = temp_dir / download.suggested_filename
                        await download.save_as(temp_path)
                        
                        if temp_path.exists() and temp_path.stat().st_size > 0:
                            # Process the downloaded file
                            file_results = await extraction_service.process_file_async(temp_path)
                            for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results:
                                processed_files.append(
                                    (file_content, filename, link_url, preview_chars, original_bytes)
                                )
                            logging.info(f"Downloaded and processed announcement file: {filename}")
                        else:
                            logging.error(f"Downloaded file {filename} is empty or missing.")
                
                except Exception as e:
                    logging.error(f"Failed to download {filename}: {str(e)}")

                # Add short delay to avoid rate-limiting
                await page.wait_for_timeout(random.uniform(800, 1500))

        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

        return processed_files

    async def find_updates(
        self,
        tenders_to_monitor: List[TenderAnalysisResult]  # type: ignore
    ) -> Dict[str, List[Tuple[str, bytes, str, str]]]:
        """
        For each tender, check if new announcements have appeared since the
        tender's last updated_at (or created_at if updated_at is None).
        
        For each new announcement:
          - If it has attachments, download and extract them.
          - Also create a text file from the announcement text.
        
        Returns:
            {
              "tender_id_str": [
                (filename, file_content, file_url), ...
              ],
              ...
            }
        """
        updates_found: Dict[str, List[Tuple[str, bytes, str, str]]] = {}

        # A single playwright context for all checks
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            for tender in tenders_to_monitor:
                tender_id_str = str(tender.id) if tender.id else "unknown_id"
                updates_found[tender_id_str] = []

                # Determine the "last check" timestamp
                last_update_ts = tender.updated_at or tender.created_at
                if not last_update_ts:
                    # As a fallback, treat everything as new if no timestamps are set
                    last_update_ts = datetime.min

                # Open a page for this tender
                detail_page = await context.new_page()
                try:
                    logging.info(f"Checking announcements for tender: {tender.tender_url}")
                    await detail_page.goto(tender.tender_url, wait_until='networkidle', timeout=30000)

                    # Parse the announcements table
                    content_html = await detail_page.content()
                    soup = BeautifulSoup(content_html, 'html.parser')
                    
                    # Check if any announcements exist
                    err_span = soup.select_one("span.errorRow")
                    if err_span and "has not publish any additional messages" in err_span.get_text(strip=True):
                        logging.info(f"No announcements found for tender ID = {tender_id_str}")
                        continue

                    # Each announcement is in a <tr>
                    announcement_rows = soup.select("#comments_info table.table tbody tr")
                    if not announcement_rows:
                        logging.info(f"No announcements table rows found for tender ID = {tender_id_str}")
                        continue

                    for row in announcement_rows:
                        try:
                            # Extract date/time
                            date_block = row.select_one("div.flex.items-center")
                            if not date_block:
                                continue
                            # Usually looks like: 2025-02-26 (span)13:41:13
                            # We'll read the text bits
                            text_parts = date_block.get_text(separator=" ", strip=True).split()
                            # e.g. ['2025-02-26', '13:41:13']
                            if len(text_parts) < 2:
                                continue

                            dt_str = text_parts[0] + " " + text_parts[1]  # 'YYYY-MM-DD HH:MM:SS'
                            try:
                                announcement_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                            except Exception:
                                logging.error(f"Could not parse announcement datetime: {dt_str}")
                                continue

                            # Compare with last_update_ts
                            if announcement_dt <= last_update_ts:
                                # This announcement is not new, skip it
                                continue

                            # This is a new announcement -> parse message text and attachments
                            td_cells = row.find_all("td")
                            if len(td_cells) < 3:
                                continue
                            # The third cell is usually the message text + attachments
                            message_cell = td_cells[2]
                            message_text = message_cell.get_text(separator="\n", strip=True)

                            # Collect attachments (if any)
                            attachment_links = []
                            link_elements = message_cell.select("ul.on-file-list li a")
                            for link_elem in link_elements:
                                href = link_elem.get("href", "").strip()
                                if href:
                                    attachment_links.append(href)

                            # If there's text in the announcement, store it as a .txt file
                            # (Even if there are attachments, we'll still store the text.)
                            if message_text:
                                # Construct a filename
                                # Example: "announcement_20250226_134113.txt"
                                dt_suffix = announcement_dt.strftime("%Y%m%d_%H%M%S")
                                text_filename = f"announcement_{dt_suffix}.txt"
                                text_bytes = message_text.encode("utf-8")

                                # Ensure consistent tuple structure (5 elements)
                                # Use text_bytes for both file_content and original_bytes
                                # Add None or empty string for preview_chars (4th element)
                                updates_found[tender_id_str].append(
                                    (text_bytes, text_filename, tender.tender_url, "", text_bytes)
                                )

                            # If there are attachments, download and extract them
                            if attachment_links:
                                # Use our new method to download and process
                                downloaded_files = await self.extract_announcement_files(detail_page, attachment_links)
                                # downloaded_files is List[Tuple[bytes, str, str]] - This comment seems outdated based on usage
                                # Usage expects: List[Tuple[bytes, str, str, str, bytes]] -> (file_content, filename, url, preview_chars, original_bytes)
                                for (file_content, filename, file_url, preview_chars, original_bytes) in downloaded_files:
                                    updates_found[tender_id_str].append(
                                        (file_content, filename, file_url, preview_chars, original_bytes)
                                    )

                            logging.info(f"[find_updates] Finished processing announcement {message_text[:50]} from {dt_str}.")
                        except Exception as ex_row:
                            logging.error(f"Error parsing announcement row: {str(ex_row)}")
                except Exception as ex_page:
                    logging.error(f"Error loading detail page for tender {tender_id_str}: {str(ex_page)}")
                finally:
                    await detail_page.close()

            await context.close()
            await browser.close()

        return updates_found