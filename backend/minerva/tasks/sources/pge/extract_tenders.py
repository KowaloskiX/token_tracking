import logging
from datetime import datetime
import os
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from playwright.async_api import async_playwright
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender

class PGETenderExtractor:
    """
    An extractor for the SWPP2 GKPGE public current tender notices page:
      https://swpp2.gkpge.pl/app/demand/notice/public/current/list?USER_MENU_HOVER=currentNoticeList

    This extractor:
      - Clicks the "Termin publikacji" header to sort tenders by newest.
      - Extracts tender data from the table with id "publicList".
      - Uses standard pagination (clicking the "Następny" link) up to a maximum of max_pages.
      - Stops scraping if a tender's publication date is older than a given start_date.
      - Includes a placeholder for file extraction from a tender detail page.
    """
    def __init__(self, source_type: str = "pge"):
        self.base_list_url = "https://swpp2.gkpge.pl/app/demand/notice/public/current/list?USER_MENU_HOVER=currentNoticeList"
        self.source_type = source_type

    async def _goto_with_retry(self, page, url: str, wait_until: str, timeout: int, retries: int = 2, purpose: str = "navigation"):
        for attempt in range(retries + 1):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return
            except Exception as e:
                if attempt < retries:
                    logging.info(f"{self.source_type}: Retrying URL {url} (attempt {attempt+1}) for {purpose}")
                else:
                    logging.error(f"{self.source_type}: Error loading URL {url} for {purpose}")
                    raise e

    async def extract_files_from_detail_page(self, context, details_url: str) -> List[Tuple[bytes, str, Optional[str], Optional[str]]]:

        processed_files = []
        extraction_service = FileExtractionService()
        page = await context.new_page()
        unique_id = str(uuid4())
        temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            await page.goto(details_url, wait_until='networkidle', timeout=20000)
            
            # 1. Extract tender description text from the designated container.
            try:
                tender_text = (await page.inner_text("div#innerContent")).strip()
            except Exception as e:
                logging.error(f"Error extracting tender description from {details_url}: {e}")
                tender_text = ""
            
            desc_filename = "tender_description.txt"
            desc_path = temp_dir / desc_filename
            with open(desc_path, "w", encoding="utf-8") as f:
                f.write(tender_text)
            
            # Use async wrapper
            desc_results = await extraction_service.process_file_async(desc_path)
            for file_content, filename, preview_chars, original_bytes, original_filename in desc_results:
                processed_files.append((file_content, filename, details_url, preview_chars, original_bytes))
            
            # 2. Locate the attachments table rows (each representing a file).
            rows = await page.query_selector_all("tr.fileDataRow")
            for row in rows:
                try:
                    # Optionally retrieve a file name for logging/debugging.
                    file_name_text = await row.inner_text()
                    
                    # Trigger the download by clicking on the attachment row.
                    async with page.expect_download(timeout=20000) as download_info:
                        await row.click()
                    download = await download_info.value
                    suggested_name = download.suggested_filename or "document"
                    file_path = temp_dir / suggested_name
                    await download.save_as(str(file_path))
                    
                    # Optionally, get the download URL from jQuery data attached to the row.
                    download_url = await page.evaluate('(element) => $(element).data("downloadUrl")', row)
                    if not download_url:
                        download_url = details_url  # Fallback
                    
                    # Use async wrapper
                    processed_attachment_results = await extraction_service.process_file_async(file_path)
                    for file_content, filename, preview_chars, original_bytes, original_filename in processed_attachment_results:
                        processed_files.append((file_content, filename, download_url, preview_chars, original_bytes))
                except Exception as e:
                    logging.error(f"Error downloading attachment from {details_url}: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error processing detail page {details_url}: {e}")
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            await page.close()
        
        return processed_files

    async def execute(self, inputs: Dict) -> Dict:
        """
        Main extraction routine.

        Steps:
        1. Navigate to the list page.
        2. Click the "Termin publikacji" column header to sort by newest.
        3. Loop over the tender rows from the table #publicList:
            - Extract tender number, name, publication date (9th cell) and submission deadline (10th cell).
            - Parse these dates (formats: "%d-%m-%Y" for publication and "%d-%m-%Y %H:%M" for deadline).
            - Stop processing if a tender's publication date is older than the provided start_date.
            - Instead of building a detail URL via string formatting, first try to get it from the row's HTML
            (data attribute or inner <a>). If not available, open a new page, click on the row and capture the URL.
        4. Handle pagination by clicking the "Następny" link (up to max_pages).
        5. Return a dictionary containing the list of tenders and metadata.
        """
        start_date_str = inputs.get("start_date", None)
        max_pages = inputs.get("max_pages", 10)
        tender_names_index_name = inputs.get('tender_names_index_name', "tenders")
        embedding_model = inputs.get('embedding_model', "text-embedding-3-large")
        start_dt = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                logging.info(f"{self.source_type}: Using start_date {start_date_str}")
            except ValueError:
                logging.error(f"{self.source_type}: Invalid start_date format: {start_date_str}")

        tenders = []
        current_page = 1

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                logging.info(f"{self.source_type}: Navigating to {self.base_list_url}")
                await self._goto_with_retry(page, self.base_list_url, wait_until='networkidle', timeout=15000, purpose="list page")

                # Click the "Termin publikacji" header to sort by newest.
                sort_header = await page.query_selector("th[data-mpgrid-id='publicationDate'] a")
                if sort_header:
                    await sort_header.click()
                    await page.wait_for_timeout(2000)
                    logging.info(f"{self.source_type}: Sorted tenders by publication date.")

                while True:
                    await page.wait_for_timeout(2000)
                    rows = await page.query_selector_all("table#publicList tr.dataRow")
                    if not rows:
                        logging.info(f"{self.source_type}: No tender rows found on page {current_page}.")
                        break

                    for row in rows:
                        try:
                            # Get the row's id (used later if needed).
                            row_id = await row.get_attribute("id")  # e.g. "96084"
                            cells = await row.query_selector_all("td")
                            if len(cells) < 10:
                                continue
                            tender_number = (await cells[0].inner_text()).strip()
                            tender_name = (await cells[1].inner_text()).strip()
                            pub_date_text = (await cells[8].inner_text()).strip()
                            deadline_text = (await cells[9].inner_text()).strip()

                            try:
                                publication_date = datetime.strptime(pub_date_text, "%d-%m-%Y")
                            except ValueError:
                                logging.error(f"{self.source_type}: Could not parse publication date: {pub_date_text}")
                                publication_date = datetime.now()

                            try:
                                submission_deadline = datetime.strptime(deadline_text, "%d-%m-%Y %H:%M")
                            except ValueError:
                                logging.error(f"{self.source_type}: Could not parse submission deadline: {deadline_text}")
                                submission_deadline = datetime.now()
                            final_pub_dt = publication_date
                            # Pinecone check for tenders older than start_dt
                            detail_url = f"https://swpp2.gkpge.pl/app/demand/notice/public/{row_id}/details"
                            if start_dt and final_pub_dt and final_pub_dt < start_dt:
                                try:
                                    query_config = QueryConfig(
                                        index_name=tender_names_index_name,
                                        namespace="",
                                        embedding_model=embedding_model
                                    )
                                    query_tool = QueryTool(config=query_config)
                                    filter_conditions = {"details_url": detail_url}
                                    default_index_results = await query_tool.query_by_id(
                                        id=detail_url,
                                        top_k=1,
                                        filter_conditions=filter_conditions
                                    )
                                    if default_index_results.get("matches"):
                                        logging.info(f"{self.source_type}: Encountered tender dated {publication_date} older than start_date {start_date_str} and found in Pinecone. Stopping extraction.")
                                        raise StopIteration
                                    else:
                                        # Not in Pinecone, include but set initiation_date to start_dt
                                        init_date_str = start_dt.strftime("%Y-%m-%d")
                                        tender_data = {
                                            "name": tender_name,
                                            "organization": "",  # Could be enriched from the details page if needed.
                                            "location": "",
                                            "submission_deadline": submission_deadline.strftime("%Y-%m-%d"),
                                            "initiation_date": init_date_str,
                                            "details_url": detail_url,
                                            "content_type": "tender",
                                            "source_type": self.source_type,
                                        }
                                        try:
                                            t_obj = Tender(**tender_data)
                                            tenders.append(t_obj)
                                            logging.info(f"{self.source_type}: Encountered tender dated {publication_date} older than start_date {start_date_str} but not found in Pinecone. Saving tender...")
                                        except Exception as te:
                                            logging.error(f"Error creating Tender object for {self.source_type} at URL: {detail_url}")
                                        continue  # Continue to next row
                                except Exception as e:
                                    logging.error(f"{self.source_type}: Error querying Pinecone when checking older tender: {e}")
                                    raise StopIteration

                            # # Stop processing if tender is older than start_dt.
                            # if start_dt and publication_date < start_dt:
                            #     logging.info(f"{self.source_type}: Tender {tender_number} (pub. {publication_date}) is older than start_date {start_dt}.")
                            #     raise StopIteration

                            # Instead of constructing detail_url via f-string, try to extract it:

                            tender_data = {
                                "name": tender_name,
                                "organization": "",  # Could be enriched from the details page if needed.
                                "location": "",
                                "submission_deadline": submission_deadline.strftime("%Y-%m-%d"),
                                "initiation_date": publication_date.strftime("%Y-%m-%d"),
                                "details_url": detail_url,
                                "content_type": "tender",
                                "source_type": self.source_type,
                            }
                            tenders.append(Tender(**tender_data))
                            logging.info(f"{self.source_type}: Extracted tender {tender_number} – {tender_name}")
                        except StopIteration:
                            raise
                        except Exception as e:
                            logging.error(f"{self.source_type}: Error processing row: {str(e)}")
                            continue

                    if current_page >= max_pages:
                        logging.info(f"{self.source_type}: Reached max page limit ({max_pages}).")
                        break

                    # Click the "Następny" link from the paginator.
                    next_page_link = await page.query_selector("ul.mp_paginator li a[title='Następny']")
                    if next_page_link:
                        await next_page_link.click()
                        await page.wait_for_timeout(3000)
                        current_page += 1
                        logging.info(f"{self.source_type}: Moved to page {current_page}.")
                    else:
                        logging.info(f"{self.source_type}: 'Następny' link not found; ending pagination.")
                        break

                await page.close()
                await browser.close()
                metadata = ExtractorMetadata(total_tenders=len(tenders), pages_scraped=current_page)
                return {"tenders": tenders, "metadata": metadata}
        except StopIteration:
            logging.info(f"{self.source_type}: Stopping due to tender publication date condition.")
            metadata = ExtractorMetadata(total_tenders=len(tenders), pages_scraped=current_page)
            return {"tenders": tenders, "metadata": metadata}
        except Exception as e:
            logging.error(f"{self.source_type}: Critical error: {str(e)}")
            raise e