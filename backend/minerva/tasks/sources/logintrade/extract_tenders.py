import logging
from datetime import datetime, timedelta
import os
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from playwright.async_api import async_playwright

from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender


class LoginTradeExtractor:
    """
    A tender extractor for the listing at https://platformazakupowa.logintrade.pl/
    demonstrating how to:
      - parse the main listing table (#offers-table)
      - fetch detail info from the tender detail page
      - download attachments
      - skip tenders older than a given start_date
    """

    def __init__(
        self,
        base_url: str = "https://platformazakupowa.logintrade.pl/",
        source_type: str = "logintrade"
    ):
        self.base_url = base_url.rstrip("/")
        self.source_type = source_type

        # You can append extra query params here (e.g. &sort=o.created_at&direction=desc)
        # if you want to list the most recent first. 
        self.list_url = (
            f"{self.base_url}/"
            "?sort=o.created_at&direction=desc&limit=10"
        )

    async def fetch_detail_info(
        self,
        context,
        detail_url: str
    ) -> dict:
        """
        Extract additional info from the detail page, e.g. full name of the organization,
        location, expanded description, etc. We'll also parse addresses, 
        or any other fields that are only available inside the detail page.
        """
        page = await context.new_page()
        detail_info = {
            "org_name": "",
            "location": "",
            "description": "",
            # If needed, store publication_dt here; 
            # but typically we get that from listing.
        }

        try:
            await page.goto(detail_url, wait_until='networkidle', timeout=20000)

            # -- Organization and location --
            # From the "Zamawiający" section:
            buyer_data = await page.query_selector("#buyerData")
            if buyer_data:
                # e.g. "H. Cegielski – Fabryka Pojazdów Szynowych Sp. z o.o."
                org_label = await buyer_data.query_selector("#buyerInfo .label")
                if org_label:
                    detail_info["org_name"] = (await org_label.inner_text()).strip()

                # The next .field elements might hold address lines.
                # e.g. "ul. 28 Czerwca 1956r nr 223/229", "61-485 Poznań", "NIP: 7831304054"
                fields = await buyer_data.query_selector_all("#buyerInfo .field")
                address_lines = []
                for f in fields:
                    txt = (await f.inner_text()).strip()
                    # Skip lines like 'NIP: 7831304054' if you only want address
                    if txt.lower().startswith("nip:"):
                        continue
                    address_lines.append(txt)
                if address_lines:
                    detail_info["location"] = ", ".join(address_lines)

            # -- Description (Treść zapytania) --
            content_section = await page.query_selector("#sectionContent .dataField.infoHeader + .dataField .label ~ div")
            # The above tries to grab the big chunk of HTML under "Treść zapytania".
            if content_section:
                detail_info["description"] = (await content_section.inner_text()).strip()

        except Exception as e:
            logging.error(f"[LoginTradeTenderExtractor] Error fetching detail info from {detail_url}: {str(e)}")
        finally:
            await page.close()

        return detail_info
    
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
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        temp_dir: Optional[Path] = None

        try:
            # Go to the detail URL
            await page.goto(details_url, wait_until='networkidle', timeout=20000)

            # "Accept"/ "Continue"/"Close" button. If there's no popup, we'll just skip.
            popup_wrapper_selector = "#infoPanel"
            popup_close_button_selector = ".buttonLogowanie"

            try:
                popup_wrapper = await page.wait_for_selector(
                    popup_wrapper_selector,
                    state="visible",
                    timeout=5000
                )
                if popup_wrapper:
                    # Now find the close button within that popup
                    close_btn = await popup_wrapper.query_selector(popup_close_button_selector)
                    if close_btn:
                        await close_btn.click()
                        # Optionally wait for the network or something else
                        await page.wait_for_load_state("networkidle")
                        logging.info("Popup found and dismissed.")
            except Exception as e:
                # No popup or the popup wasn't found within 3s; proceed
                pass

            # Prepare a temp dir for downloads and the description text file
            unique_id = str(uuid4())
            temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
            temp_dir.mkdir(parents=True, exist_ok=True)

            # 1) Extract *all* textual content from the page and save it as tender_description.txt
            desc_text = ""
            try:
                # This grabs everything in the <body> element.
                desc_text = (await page.inner_text("body")).strip()
            except Exception as e:
                logging.error(f"Failed to grab page text: {str(e)}")

            desc_filename = "tender_description.txt"
            desc_path = temp_dir / desc_filename

            try:
                with open(desc_path, "w", encoding="utf-8") as f:
                    f.write(desc_text)

                # Process the .txt file (so the text gets included in your extraction pipeline)
                desc_results = await extraction_service.process_file_async(desc_path)
                # We store `details_url` as the "download_url" for the description
                for (file_content, filename, preview_chars, original_bytes, original_filename) in desc_results:
                    processed_files.append((file_content, filename, details_url, preview_chars, original_bytes))
                    logging.info(f"{self.source_type}: Processed description for {unique_id}")

            except Exception as e:
                logging.error(
                    f"[LoginTradeTenderExtractor] Failed to create/read the "
                    f".txt file for description: {str(e)}"
                )

            # 2) Extract file attachments from the page's "Załączniki" table
            attachments_table = await page.query_selector("table#contentAtatachmentsList")
            if attachments_table:
                rows = await attachments_table.query_selector_all("tr")
                for row in rows:
                    try:
                        link = await row.query_selector("a[href^='DocumentService']")
                        if not link:
                            continue
                        href = await link.get_attribute("href")
                        if not href:
                            continue

                        # Build full download URL if relative
                        from urllib.parse import urljoin
                        download_url = urljoin(details_url, href)

                        # Trigger the download via playwright
                        async with page.expect_download(timeout=20000) as download_info:
                            await link.click()
                            download = await download_info.value

                        suggested_name = download.suggested_filename or "document"
                        temp_path = temp_dir / suggested_name
                        await download.save_as(str(temp_path))

                        # Process the downloaded file
                        file_results = await extraction_service.process_file_async(temp_path)
                        for file_content, filename, preview_chars, original_bytes, original_filename in file_results:
                            processed_files.append(
                                (file_content, filename, download_url, preview_chars, original_bytes)
                            )
                            logging.info(f"{self.source_type}: Downloaded and processed {suggested_name}")

                    except Exception as e:
                        logging.error(
                            f"[LoginTradeTenderExtractor] Error downloading file from "
                            f"{details_url}: {str(e)}"
                        )
                        continue
            # 3) In addition, extract file attachments from any <ul class="zalaczniki"> list
            attachments_list = await page.query_selector("ul.zalaczniki")
            if attachments_list:
                list_items = await attachments_list.query_selector_all("li")
                for item in list_items:
                    try:
                        link = await item.query_selector("a[href^='DocumentService']")
                        if not link:
                            continue

                        href = await link.get_attribute("href")
                        if not href:
                            continue

                        from urllib.parse import urljoin
                        download_url = urljoin(details_url, href)

                        async with page.expect_download(timeout=20000) as download_info:
                            await link.click()
                            download = await download_info.value

                        suggested_name = download.suggested_filename or "document"
                        temp_path = temp_dir / suggested_name
                        await download.save_as(str(temp_path))

                        # Process the downloaded file
                        file_results = await extraction_service.process_file_async(temp_path)
                        for file_content, filename, preview_chars, original_bytes, original_filename in file_results:
                            processed_files.append(
                                (file_content, filename, download_url, preview_chars, original_bytes)
                            )
                            logging.info(f"{self.source_type}: Downloaded and processed updated file {suggested_name}")

                    except Exception as e:
                        logging.error(
                            f"[LoginTradeTenderExtractor] Error downloading attachment "
                            f"from <ul.zalaczniki> for {details_url}: {str(e)}"
                        )
                        continue

            logging.info(
                f"[LoginTradeTenderExtractor] Extracted {len(processed_files)} "
                f"file(s) from {details_url}"
            )

        except Exception as e:
            logging.error(
                f"[LoginTradeTenderExtractor] Error opening detail page for file extraction {details_url}: {str(e)}"
            )
        finally:
            # Clean up
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            await page.close()

        return processed_files

    async def execute(self, inputs: Dict) -> Dict:
        """
        Main scraping routine. Expects:
            {
                "max_pages": int (maximum number of listing pages),
                "start_date": str in 'YYYY-MM-DD' format (optional, skip older tenders)
            }
        Returns:
            {
                "tenders": [Tender, ...],
                "metadata": ExtractorMetadata(...)
            }
        """
        max_pages = inputs.get("max_pages", 10)
        start_date_str = inputs.get("start_date", None)

        start_dt = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                logging.info(f"[LoginTradeTenderExtractor] Start date = {start_dt}")
            except ValueError:
                logging.error(f"[LoginTradeTenderExtractor] Invalid date format for 'start_date': {start_date_str}")

        async with async_playwright() as p:
            # Launch the browser
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()

                logging.info(f"[LoginTradeTenderExtractor] Navigating to {self.list_url}")
                await page.goto(self.list_url, wait_until='networkidle', timeout=20000)

                tenders = []
                current_page = 1

                while current_page <= max_pages:
                    logging.info(f"[LoginTradeTenderExtractor] Scraping page {current_page}/{max_pages}...")

                    # Rows in the listing:
                    #   <tbody><tr>...
                    #     <td class="name"> 
                    #        <div class="blue-header">
                    #           <a href="...">TITLE</a>
                    #        </div>
                    #        <div class="label">REFERENCE</div>
                    #        <div class="company">ORGANIZATION</div>
                    #     </td>
                    #     <td class="date">Data publikacji... 14.02.2025 / 17:12</td>
                    #     <td class="date">Data złożenia oferty... 19.02.2025 / 13:00</td>
                    #   </tr>
                    rows = await page.query_selector_all("#offers-table table tbody tr")
                    if not rows:
                        logging.info("[LoginTradeTenderExtractor] No more rows found; stopping.")
                        break

                    for row in rows:
                        try:
                            # Name & detail link
                            header_el = await row.query_selector("td.name div.blue-header a")
                            if not header_el:
                                continue
                            name = (await header_el.inner_text()).strip()
                            details_href = await header_el.get_attribute("href") or ""

                            # Example: "https://fpspoznan.logintrade.net/portal,szczegolyZapytaniaOfertowe,b049f1c57197ad8ef7b5a9d938ee6dc4.html"
                            detail_url = details_href if details_href.startswith("http") else self.base_url + details_href

                            # Reference / label (e.g. "Z12/1582/1")
                            label_el = await row.query_selector("td.name div.label")
                            reference_str = (await label_el.inner_text()).strip() if label_el else ""

                            # Organization (e.g. "H. Cegielski - Fabryka Pojazdów Szynowych Sp. z o.o")
                            org_el = await row.query_selector("td.name div.company")
                            org_text = (await org_el.inner_text()).strip() if org_el else ""

                            # Publication date (14.02.2025 17:12). It's in the 2nd td.date
                            pub_date_td = await row.query_selector_all("td.date")
                            publication_date_str = ""
                            submission_date_str = ""
                            if len(pub_date_td) >= 1:
                                # 1st date td => "Data publikacji"
                                pub_divs = await pub_date_td[0].query_selector_all("div.date, div.time")
                                # Typically 2 lines: "14.02.2025" and "17:12"
                                if len(pub_divs) >= 2:
                                    date_str = (await pub_divs[0].inner_text()).strip()  # e.g. "14.02.2025"
                                    time_str = (await pub_divs[1].inner_text()).strip()  # e.g. "17:12"
                                    publication_date_str = f"{date_str} {time_str}"

                            if len(pub_date_td) >= 2:
                                # 2nd date td => "Data złożenia oferty"
                                sub_divs = await pub_date_td[1].query_selector_all("div.date, div.time")
                                if len(sub_divs) >= 2:
                                    date_str = (await sub_divs[0].inner_text()).strip()  # e.g. "19.02.2025"
                                    time_str = (await sub_divs[1].inner_text()).strip()  # e.g. "13:00"
                                    submission_date_str = f"{date_str} {time_str}"

                            # Convert "14.02.2025 17:12" => "2025-02-14 17:12:00"
                            # Use DateStandardizer or direct strptime.
                            publication_dt = None
                            if publication_date_str:
                                try:
                                    publication_dt = datetime.strptime(publication_date_str, "%d.%m.%Y %H:%M")
                                except ValueError:
                                    logging.warning(f"Could not parse publication date from '{publication_date_str}'")

                            submission_dt = None
                            if submission_date_str:
                                try:
                                    submission_dt = datetime.strptime(submission_date_str, "%d.%m.%Y %H:%M")
                                except ValueError:
                                    logging.warning(f"Could not parse submission date from '{submission_date_str}'")

                            # If we have a start_dt, skip if publication_dt < start_dt
                            if start_dt and publication_dt and (publication_dt < start_dt):
                                logging.info(f"Skipping older tender '{name}' published at {publication_dt}")
                                continue

                            # Next: gather detail info
                            detail_info = {}
                            if detail_url:
                                detail_info = await self.fetch_detail_info(context, detail_url)

                            # If the detail page has a more precise org name, override
                            org_name = detail_info.get("org_name") or org_text
                            location = detail_info.get("location", "")
                            # We'll store the listing's publication date as "initiation_date"
                            # or we can also store it in the tender object "publication_date" if needed.

                            init_date_str = ""
                            if publication_dt:
                                init_date_str = publication_dt.strftime("%Y-%m-%d")

                            # Convert submission_dt to standard format for the model
                            submission_deadline_str = ""
                            if submission_dt:
                                submission_deadline_str = submission_dt.strftime("%Y-%m-%d %H:%M:%S")

                            # Build our Tender object
                            tender_data = {
                                "name": name,                 # e.g. "Elementy elektryczne EAO"
                                "organization": org_name,      # e.g. "H. Cegielski - Fabryka Pojazdów Szynowych"
                                "location": location,          # e.g. "ul. 28 Czerwca 1956r nr 223/229, 61-485 Poznań"
                                "submission_deadline": submission_deadline_str,  # "2025-02-19 13:00:00"
                                "initiation_date": init_date_str,                # "2025-02-14"
                                "details_url": detail_url,
                                "content_type": "tender",
                                "source_type": self.source_type,
                                # (Optionally store reference / label, or put it in name)
                                # "reference_code": reference_str,
                            }

                            # Create the Tender pydantic model (assuming you have that in your environment)
                            try:
                                tender_obj = Tender(**tender_data)
                                tenders.append(tender_obj)
                                logging.info(f"Extracted tender: [{reference_str}] {name} (org={org_name})")
                            except Exception as err:
                                logging.error(f"Error creating Tender object: {err}")
                                continue

                        except Exception as e:
                            logging.error(f"Error parsing row on page {current_page}: {e}")
                            continue

                    # Move to the next page if there's a link with class="navigation next"
                    next_link = await page.query_selector(".pagination-links a.navigation.next")
                    if next_link:
                        await next_link.click()
                        await page.wait_for_selector("#offers-table table tbody tr", timeout=15000)
                        current_page += 1
                    else:
                        # no more pages
                        break

                metadata = ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=current_page
                )
                logging.info(f"[LoginTradeTenderExtractor] Extraction complete. Found {len(tenders)} tenders.")

                return {
                    "tenders": tenders,
                    "metadata": metadata
                }

            finally:
                # Clean up the browser in a finally block to ensure it's always closed
                await browser.close()

    async def find_updates(
        self,
        tenders_to_monitor: List[TenderAnalysisResult]
    ) -> Dict[str, List[Tuple[str, bytes, str]]]:
        """
        For each tender in `tenders_to_monitor`, checks the attachments table on the detail page.
        Compares each attachment's date (the 4th <td> in each row) to the tender's last `updated_at`,
        or `created_at` if `updated_at` is None. If the attachment's date is newer, it is downloaded
        and added to the returned dictionary.

        Returns:
            {
                "tender_id_str": [
                    (filename, file_content, file_url),  # for each newly found attachment
                    ...
                ],
                ...
            }
        """
        logging.info(f"[LoginTradeExtractor.find_updates] Starting update check for {len(tenders_to_monitor)} tenders")
        updates_found: Dict[str, List[Tuple[str, bytes, str]]] = {}
        total_new_attachments = 0

        # Reuse the same approach as in extract_files_from_detail_page for file processing
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        async with async_playwright() as p:
            logging.debug("[LoginTradeExtractor.find_updates] Initializing Playwright browser")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            try:
                for index, tender in enumerate(tenders_to_monitor):
                    # Convert the tender's ObjectId (or any ID) to string for dict key
                    tender_id_str = str(tender.id)
                    logging.info(f"[LoginTradeExtractor.find_updates] Processing tender {tender_id_str} ({index+1}/{len(tenders_to_monitor)})")

                    # The date to compare against
                    compare_dt = tender.updated_at or tender.created_at
                    if not compare_dt:
                        # If, for some reason, there's no created_at, skip
                        logging.warning(f"[LoginTradeExtractor.find_updates] Tender {tender_id_str} has no compare date (updated_at or created_at). Skipping.")
                        continue

                    logging.debug(f"[LoginTradeExtractor.find_updates] Using comparison date {compare_dt} for tender {tender_id_str}")

                    # Open a new page for each tender's detail URL
                    page = await context.new_page()

                    try:
                        detail_url = tender.tender_url
                        logging.debug(f"[LoginTradeExtractor.find_updates] Navigating to detail page: {detail_url}")
                        await page.goto(detail_url, wait_until='networkidle', timeout=20000)

                        # Dismiss any popup if present (similar to extract_files_from_detail_page)
                        try:
                            logging.debug(f"[LoginTradeExtractor.find_updates] Checking for popup on page for tender {tender_id_str}")
                            popup_wrapper = await page.wait_for_selector(
                                "#infoPanel",
                                state="visible",
                                timeout=5000
                            )
                            if popup_wrapper:
                                logging.debug(f"[LoginTradeExtractor.find_updates] Dismissing popup for tender {tender_id_str}")
                                close_btn = await popup_wrapper.query_selector(".buttonLogowanie")
                                if close_btn:
                                    await close_btn.click()
                                    await page.wait_for_load_state("networkidle")
                        except:
                            # No popup found in time, ignore
                            logging.debug(f"[LoginTradeExtractor.find_updates] No popup found for tender {tender_id_str}")
                            pass

                        # Locate the attachments table by its selector
                        logging.debug(f"[LoginTradeExtractor.find_updates] Looking for attachments table for tender {tender_id_str}")
                        attachments_table = await page.query_selector("table#contentAtatachmentsList")
                        if not attachments_table:
                            # No attachments table => no updates
                            logging.info(f"[LoginTradeExtractor.find_updates] No attachments table found for tender {tender_id_str}")
                            updates_found[tender_id_str] = []
                            continue

                        rows = await attachments_table.query_selector_all("tr")
                        logging.info(f"[LoginTradeExtractor.find_updates] Found {len(rows)} attachment rows for tender {tender_id_str}")

                        newly_downloaded: List[Tuple[str, bytes, str]] = []
                        temp_dir = Path(os.getcwd()) / f"temp_logintrade_{tender_id_str}"
                        temp_dir.mkdir(exist_ok=True)
                        logging.debug(f"[LoginTradeExtractor.find_updates] Created temp directory at {temp_dir}")

                        for row_index, row in enumerate(rows):
                            # Attempt to locate the download link and the date cell
                            link = await row.query_selector("a[href^='DocumentService']")
                            if not link:
                                logging.debug(f"[LoginTradeExtractor.find_updates] Row {row_index} has no download link. Skipping.")
                                continue

                            cells = await row.query_selector_all("td")
                            if len(cells) < 4:
                                # We expect at least 4 <td>: icon, filename, size, upload_date
                                logging.debug(f"[LoginTradeExtractor.find_updates] Row {row_index} has insufficient cells ({len(cells)}). Skipping.")
                                continue

                            # The 4th <td> should have the datetime in format: "2025-02-26 14:10:26"
                            date_text = (await cells[3].inner_text()).strip()
                            if not date_text:
                                logging.debug(f"[LoginTradeExtractor.find_updates] Row {row_index} has empty date cell. Skipping.")
                                continue

                            # Parse the date
                            try:
                                attachment_dt = datetime.strptime(date_text, "%Y-%m-%d %H:%M:%S")
                                logging.debug(f"[LoginTradeExtractor.find_updates] Row {row_index} has attachment date: {attachment_dt}")
                            except ValueError:
                                # If parsing fails, skip
                                logging.warning(f"[LoginTradeExtractor.find_updates] Failed to parse date '{date_text}' for row {row_index}. Skipping.")
                                continue

                            # Compare with tender's compare_dt
                            if attachment_dt <= compare_dt:
                                # Not newer => skip
                                logging.info(f"[LoginTradeExtractor.find_updates] Attachment date {attachment_dt} is not newer than tender date {compare_dt}. Skipping.")
                                continue

                            logging.info(f"[LoginTradeExtractor.find_updates] Found newer attachment for tender {tender_id_str}: {attachment_dt} > {compare_dt}")

                            # If we got here, the attachment is newer => download
                            href = await link.get_attribute("href")
                            if not href:
                                logging.warning(f"[LoginTradeExtractor.find_updates] Link in row {row_index} has no href attribute. Skipping.")
                                continue

                            from urllib.parse import urljoin
                            download_url = urljoin(detail_url, href)

                            # Get filename from the second cell if possible
                            filename_text = ""
                            if len(cells) > 1:
                                filename_text = await cells[1].inner_text()
                                filename_text = filename_text.strip()
                            
                            logging.info(f"[LoginTradeExtractor.find_updates] Downloading file '{filename_text}' from {download_url}")

                            # Perform the download
                            try:
                                async with page.expect_download(timeout=20000) as download_info:
                                    await link.click()
                                    download = await download_info.value

                                suggested_name = download.suggested_filename or "document"
                                temp_path = temp_dir / suggested_name
                                await download.save_as(str(temp_path))
                                logging.info(f"[LoginTradeExtractor.find_updates] Successfully downloaded file to {temp_path}")

                                # Process the downloaded file (extract text or keep binary, etc.)
                                logging.debug(f"[LoginTradeExtractor.find_updates] Processing downloaded file {temp_path}")
                                file_results = await extraction_service.process_file_async(temp_path)
                                for file_content, filename, preview_chars, original_bytes, original_filename in file_results:
                                    newly_downloaded.append(
                                        (file_content, filename, download_url, preview_chars, original_bytes)
                                    )
                                    logging.info(f"[LoginTradeExtractor.find_updates] Processed file '{original_filename}' ({len(file_content)} bytes)")
                                    # Log a short preview of the file content for debugging
                                    if preview_chars:
                                        logging.debug(f"[LoginTradeExtractor.find_updates] Content preview: {preview_chars[:100]}...")

                            except Exception as e:
                                logging.error(
                                    f"[LoginTradeExtractor.find_updates] Error downloading file "
                                    f"for tender {tender_id_str} from {download_url}: {e}"
                                )
                                continue

                        # If we found new files, record them
                        updates_found[tender_id_str] = newly_downloaded
                        logging.info(f"[LoginTradeExtractor.find_updates] Found {len(newly_downloaded)} new attachments for tender {tender_id_str}")
                        total_new_attachments += len(newly_downloaded)

                        # Clean up temp dir
                        if temp_dir.exists():
                            logging.debug(f"[LoginTradeExtractor.find_updates] Cleaning up temp directory {temp_dir}")
                            shutil.rmtree(temp_dir, ignore_errors=True)

                    except Exception as e:
                        logging.error(
                            f"[LoginTradeExtractor.find_updates] Error processing tender {tender_id_str}: {e}"
                        )
                        # Add stack trace for better debugging
                        import traceback
                        logging.debug(f"[LoginTradeExtractor.find_updates] Stack trace: {traceback.format_exc()}")
                        updates_found[tender_id_str] = []
                    finally:
                        logging.debug(f"[LoginTradeExtractor.find_updates] Finished processing tender {tender_id_str}")
                        await page.close()

            finally:
                logging.debug("[LoginTradeExtractor.find_updates] Closing browser")
                await browser.close()

        logging.info(f"[LoginTradeExtractor.find_updates] Completed update check. Found {total_new_attachments} new attachments across {len(updates_found)} tenders")
        return updates_found