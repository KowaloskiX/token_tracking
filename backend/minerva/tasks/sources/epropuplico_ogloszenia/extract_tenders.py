import logging
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
import re

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
        # Base URL for the main listing page (no organization parameter)
        self.base_list_url = "https://e-propublico.pl/Ogloszenia"
        self.source_type = source_type

    async def fetch_detail_info(
        self,
        context,
        detail_url: str
    ) -> dict:
        """
        Fetch extra information from the detail page, such as:
         - publication_dt
         - org_name
         - location
        """
        page = await context.new_page()
        detail_info = {
            "publication_dt": None,
            "org_name": "Unknown",
            "location": "",
        }
        
        try:
            await page.goto(detail_url, wait_until='networkidle', timeout=15000)
            
            card_body = await page.query_selector("div.card-body")
            if card_body:
                # Organization name
                org_name_elem = await card_body.query_selector("h6.card-title")
                if org_name_elem:
                    detail_info["org_name"] = (await org_name_elem.inner_text()).strip()

                # Attempt to parse out location lines from the body
                divs_after_title = await card_body.query_selector_all("div")
                lines = [(await d.inner_text()).strip() for d in divs_after_title]

                address_lines = []
                for line in lines:
                    # Stop at typical contact lines
                    if any(keyword in line.lower() for keyword in ["tel.:", "faks:", "e-mail:", "adres strony internetowej"]):
                        break
                    address_lines.append(line)
                
                if len(address_lines) >= 1:
                    # e.g. "Wołoska 137, 02-507 Warszawa"
                    detail_info["location"] = ", ".join(address_lines)

            # Look for "Data publikacji: YYYY-MM-DD HH:MM:SS" in row elements
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
                            logging.error(f"Could not parse publication date string: {dt_str}")
                    else:
                        logging.warning("Could not find date after 'Data publikacji:' text.")
            
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
        """
        Extract files from the detail page. Returns a list of tuples:
        [
          (file_content_in_bytes, filename, file_url),
          ...
        ]
        """
        page = await context.new_page()
        processed_files = []
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        temp_dir = None
        
        try:
            await page.goto(details_url, wait_until='networkidle', timeout=15000)

            # Attempt to click on the "Dokumenty zamówienia" tab if present
            doc_tab_link = await page.query_selector("#navItem_dokumentyZamowienia")
            if not doc_tab_link:
                logging.info(f"No 'Dokumenty zamówienia' link found at {details_url}. No files to extract.")
                return processed_files

            async with page.expect_navigation(timeout=15000):
                await doc_tab_link.click()

            await page.wait_for_selector("table#checkable tbody tr", timeout=15000)

            # Create a temporary directory to store downloads
            unique_id = str(uuid4())
            temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
            temp_dir.mkdir(parents=True, exist_ok=True)


            rows = await page.query_selector_all("table#checkable tbody tr")
            if not rows:
                logging.info(f"No document rows found in 'Dokumenty zamówienia' table at {details_url}.")
                return processed_files

            for row in rows:
                try:
                    link = await row.query_selector("a[href*='/Dokumenty/Download/']")
                    if not link:
                        continue
                    href = await link.get_attribute("href")
                    if not href:
                        continue

                    # Construct full download URL
                    download_url = "https://e-propublico.pl" + href

                    # Perform the download
                    async with page.expect_download(timeout=15000) as download_info:
                        await link.click()
                        download = await download_info.value

                    suggested_name = download.suggested_filename or "document"
                    temp_path = temp_dir / suggested_name

                    # Move the file from Playwright's download path to our temp directory
                    download_path = await download.path()
                    shutil.move(download_path, str(temp_path))

                    # Extract the file content(s)
                    file_results = await extraction_service.process_file_async(temp_path)
                    for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results:
                        processed_files.append((file_content, filename, download_url, preview_chars, original_bytes))
                        logging.info(f"Downloaded and processed {filename}")

                except Exception as e:
                    logging.error(f"Error downloading file in row from {details_url}: {str(e)}")
                    continue

            logging.info(f"Processed {len(processed_files)} files from {details_url}")

        except Exception as e:
            logging.error(f"Error accessing detail page {details_url}: {str(e)}")
        finally:
            # Cleanup temp directory
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
                logging.info(f"Starting extraction with start_date: {start_date_str}")
            except ValueError:
                logging.error(f"Invalid date format for start_date: {start_date_str}")
                start_dt = None
        else:
            logging.info("Starting extraction with no start_date.")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            tenders = []
            current_page = 1

            # We iterate over listing pages up to max_pages
            while current_page <= max_pages:
                list_url = f"{self.base_list_url}?page={current_page}"
                page = await context.new_page()
                
                logging.info(f"Navigating to listing page: {list_url}")
                try:
                    await page.goto(list_url, wait_until='networkidle', timeout=15000)
                except Exception as e:
                    logging.error(f"Error navigating to {list_url}: {str(e)}")
                    await page.close()
                    break

                # Grab the <table> with the rows of tenders
                table = await page.query_selector("table.table")
                if not table:
                    logging.info(f"No tenders table found on page={current_page}. Stopping.")
                    await page.close()
                    break

                rows = await table.query_selector_all("tbody tr")
                if not rows:
                    logging.info(f"No rows found in tenders table on page={current_page}. Stopping.")
                    await page.close()
                    break

                # Track whether we found at least one tender that is >= start_date
                found_recent_tender = False

                for row in rows:
                    try:
                        cells = await row.query_selector_all("td")
                        if len(cells) < 4:
                            continue

                        # 1) Sygnatura
                        signature = (await cells[0].inner_text()).strip()

                        # 2) Temat (tender name) + link to detail page
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

                        # 3) Zamawiający
                        org_column_text = (await cells[2].inner_text()).strip()

                        # 4) Termin składania (split into date and time lines)
                        deadline_text = (await cells[3].inner_text()).strip().split("\n")
                        date_part = deadline_text[0].strip() if len(deadline_text) >= 1 else ""
                        time_part = deadline_text[1].strip() if len(deadline_text) >= 2 else ""
                        submission_deadline = DateStandardizer.standardize_deadline(
                            f"{date_part} {time_part}".strip()
                        )

                        # Fetch detail info for publication date, full org name, location
                        publication_dt = None
                        org_name = org_column_text  # fallback if detail not found
                        location = ""
                        if detail_url:
                            detail_info = await self.fetch_detail_info(context, detail_url)
                            publication_dt = detail_info.get("publication_dt")
                            # If detail's org_name is not "Unknown", override
                            detail_org_name = detail_info.get("org_name", "").strip()
                            if detail_org_name and detail_org_name != "Unknown":
                                org_name = detail_org_name
                            location = detail_info.get("location", "")

                        # If no publication_dt from detail, use current date as fallback
                        if not publication_dt:
                            publication_dt = datetime.now()

                        # Filter out tenders older than start_date (if start_dt is given)
                        if start_dt and publication_dt < start_dt:
                            logging.info(
                                f"Skipping tender published at {publication_dt} < start_dt={start_dt}"
                            )
                            continue
                        else:
                            found_recent_tender = True

                        # Build a Tender object
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

                        # Instantiate the Tender model
                        t_obj = Tender(**tender_data)
                        tenders.append(t_obj)
                        logging.info(
                            f"Extracted tender {signature} org='{org_name}', loc='{location}', "
                            f"published={init_date_str}"
                        )
                    except Exception as e:
                        logging.error(f"Error parsing row on page={current_page}: {str(e)}")
                        continue

                # Close current listing page
                await page.close()

                # If we found no tender meeting the date criteria,
                # we can break early to avoid scraping "forever."
                # if start_dt and not found_recent_tender:
                #     logging.info(f"No more recent tenders found on page={current_page}. Stopping early.")
                #     break

                current_page += 1  # Move to the next listing page

            await browser.close()

            metadata = ExtractorMetadata(
                total_tenders=len(tenders),
                pages_scraped=current_page - 1
            )
            
            logging.info(f"Extraction complete. Found {len(tenders)} tenders across {current_page-1} pages.")
            
            return {
                "tenders": tenders,
                "metadata": metadata
            }
