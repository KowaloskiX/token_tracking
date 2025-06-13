import logging
from datetime import datetime
import os
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from playwright.async_api import async_playwright

from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService

class LogintradeBase:

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

            # 3) Extract file attachments from any <ul class="zalaczniki"> list
            # First try the new layout with zalaczniki_nowe
            attachments_container = await page.query_selector("div.zalaczniki_nowe")
            if attachments_container:
                list_items = await attachments_container.query_selector_all("li")
                for item in list_items:
                    try:
                        link = await item.query_selector("a.zal_nazwa")
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
                            logging.info(f"{self.source_type}: Downloaded and processed new layout file {suggested_name}")

                    except Exception as e:
                        logging.error(
                            f"[LoginTradeTenderExtractor] Error downloading attachment "
                            f"from new layout for {details_url}: {str(e)}"
                        )
                        continue

            # 4) Try the old layout with direct ul.zalaczniki
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
                            logging.info(f"{self.source_type}: Downloaded and processed old layout file {suggested_name}")

                    except Exception as e:
                        logging.error(
                            f"[LoginTradeTenderExtractor] Error downloading attachment "
                            f"from old layout for {details_url}: {str(e)}"
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