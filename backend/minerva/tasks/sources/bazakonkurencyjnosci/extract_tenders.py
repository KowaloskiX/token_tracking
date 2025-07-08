import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
import re
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from playwright.async_api import async_playwright
from minerva.core.utils.date_standardizer import DateStandardizer
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender
import urllib.parse
from minerva.core.services.vectorstore.file_content_extract.base import ExtractorRegistry
# Import helper functions for BZP
from minerva.tasks.sources.helpers import extract_bzp_plan_fields, scrape_bzp_budget_row
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool


class BazaKonkurencyjnosciTenderExtractor:
    """
    Example scraper for tenders from:
    https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl/ogloszenia/szukaj

    This version ensures that pages and the browser are closed in all edge cases,
    and only key events (timeouts, retry attempts, and scraped URLs with the extractor source name)
    are logged.
    """

    def __init__(self, source_type: str = "bazakonkurencyjnosci"):
        self.list_url = "https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl/ogloszenia/szukaj"
        self.source_type = source_type

    async def _goto_with_retry(self, page, url: str, wait_until: str = 'networkidle', timeout: int = 30000, retries: int = 2):
        """
        Wrapper around page.goto that will retry if a timeout occurs.
        Logs a retry attempt and final timeout errors with the extractor source name.
        """
        for attempt in range(retries + 1):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return
            except Exception as e:
                if "Timeout" in str(e):
                    if attempt < retries:
                        logging.info(f"Retrying to load URL for {self.source_type}: {url}")
                    else:
                        logging.error(f"Timeout loading URL for {self.source_type}: {url}")
                        raise
                else:
                    raise

    async def fetch_detail_info(self, context, detail_url: str) -> dict:
        page = await context.new_page()
        detail_info = {
            "publication_dt": None,
            "org_name": "",
            "org_address": "",
            "nip": "",
        }
        try:
            await self._goto_with_retry(page, detail_url, wait_until='networkidle', timeout=30000)

            published_label = await page.query_selector(
                "div.field-with-label.announcement--date:has(p.label:has-text('Data opublikowania ogłoszenia')) p.text"
            )
            if published_label:
                pub_str = (await published_label.inner_text()).strip()
                try:
                    pub_dt = datetime.strptime(pub_str, "%Y-%m-%d")
                    detail_info["publication_dt"] = pub_dt
                except ValueError:
                    # Suppressed non-critical parse errors.
                    pass

            address_container = await page.query_selector(
                "div.field-with-label:has(p.label:has-text('Dane adresowe ogłoszeniodawcy'))"
            )
            if address_container:
                text_lines = await address_container.query_selector_all("p.text.mdc-typography--subtitle2")
                lines_str = [await t.inner_text() for t in text_lines]
                if lines_str:
                    detail_info["org_name"] = lines_str[0].strip()
                if len(lines_str) > 1:
                    detail_info["org_address"] = "\n".join(lines_str[1:])
                    for ln in lines_str[1:]:
                        if "NIP:" in ln:
                            detail_info["nip"] = ln.replace("NIP:", "").strip()
                            break

        except Exception as e:
            if "Timeout" in str(e):
                logging.error(f"Timeout loading detail info for {self.source_type} at URL: {detail_url}")
            else:
                logging.error(f"Error fetching detail info for {self.source_type} at URL: {detail_url}")
        finally:
            await page.close()

        return detail_info

    async def extract_files_from_detail_page(self, context, details_url: str) -> List[Tuple[bytes, str, Optional[str], str]]:
        processed_files = []
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        temp_dir = None
        page = None
        try:
            page = await context.new_page()
            await self._goto_with_retry(page, details_url, wait_until='networkidle', timeout=30000)

            attach_list = await page.query_selector_all("ol.attachements__list li")
            if not attach_list:
                return processed_files

            # Create a temp directory for downloads
            unique_id = str(uuid4())
            temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
            temp_dir.mkdir(parents=True, exist_ok=True)

            for li_item in attach_list:
                download_button = await li_item.query_selector("button.btn--pdf-dowload")
                if not download_button:
                    continue

                async with page.expect_download(timeout=15000) as download_info:
                    await download_button.click()
                download = await download_info.value
                suggested_name = download.suggested_filename or "document"
                temp_path = temp_dir / suggested_name
                await download.save_as(str(temp_path))
                file_results = await extraction_service.process_file_async(temp_path)
                for file_content, filename, preview_chars, original_bytes, original_filename in file_results:
                    processed_files.append((file_content, filename, details_url, preview_chars, original_bytes))

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
            if "Timeout" in str(e):
                logging.error(f"Timeout extracting files for {self.source_type} at URL: {details_url}")
            else:
                logging.error(f"Error extracting files for {self.source_type} at URL: {details_url}: {e}")
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            if page:
                await page.close()

        return processed_files

    async def execute(self, inputs: Dict) -> Dict:
        max_pages = inputs.get("max_pages", 50)
        start_date_str = inputs.get("start_date", None)
        tender_names_index_name = inputs.get('tender_names_index_name', "tenders")
        embedding_model = inputs.get('embedding_model', "text-embedding-3-large")
        start_dt = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
            except ValueError:
                logging.error(f"Invalid start_date format for {self.source_type}: {start_date_str}")
                start_dt = None

        tenders = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()
                await self._goto_with_retry(page, self.list_url, wait_until='networkidle', timeout=30000)

                # Attempt to select sort option if available (non-critical if not found)
                try:
                    sorter_control = await page.query_selector("div.selectClassName div.css-yk16xz-control")
                    if sorter_control:
                        await sorter_control.click()
                        date_option = await page.query_selector("div.css-8k4whb-option")
                        if date_option:
                            await date_option.click()
                except Exception as e:
                    if "Timeout" in str(e):
                        logging.error(f"Timeout selecting sort option for {self.source_type}")
                    # Ignore other non-critical errors.

                await page.wait_for_timeout(2000)
                current_page = 1
                while current_page <= max_pages:
                    li_items = await page.query_selector_all("li.search__item")
                    if not li_items:
                        break

                    for li_item in li_items:
                        try:
                            link_el = await li_item.query_selector("a.link-text")
                            if not link_el:
                                continue

                            name = (await link_el.inner_text()).strip()
                            rel_href = await link_el.get_attribute("href") or ""
                            detail_url = (
                                "https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl" + rel_href
                                if rel_href.startswith("/") else rel_href
                            )

                            meta_p_tags = await li_item.query_selector_all("section.grid-custom p.search__results-meta")
                            pub_date_text = ""
                            submission_deadline = ""
                            org_name = ""
                            location = ""
                            for p_tag in meta_p_tags:
                                text_val = (await p_tag.inner_text()).strip()
                                if text_val.startswith("Opublikowano:"):
                                    pub_date_text = text_val.replace("Opublikowano:", "").strip()
                                elif text_val.startswith("Termin składania ofert:"):
                                    submission_deadline = text_val.replace("Termin składania ofert:", "").strip()
                                elif text_val.startswith("Publikacja ogłoszenia:"):
                                    pub_date_text = text_val.replace("Publikacja ogłoszenia:", "").strip()
                                elif (await p_tag.get_attribute("class")) and "company-name" in (await p_tag.get_attribute("class")):
                                    span = await p_tag.query_selector("span")
                                    if span:
                                        org_name = (await span.inner_text()).strip()
                                    else:
                                        org_name = text_val
                                else:
                                    if "województwo" in text_val.lower() or "," in text_val:
                                        location = text_val

                            publication_dt = None
                            if pub_date_text:
                                for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                                    try:
                                        publication_dt = datetime.strptime(pub_date_text, fmt)
                                        break
                                    except Exception:
                                        continue


                            detail_info = await self.fetch_detail_info(context, detail_url)
                            final_pub_dt = detail_info.get("publication_dt") or publication_dt
                            if detail_info.get("org_name"):
                                org_name = detail_info["org_name"] or org_name
                            address_info = detail_info.get("org_address", "")
                            nip_val = detail_info.get("nip", "")

                            init_date_str = final_pub_dt.strftime("%Y-%m-%d") if final_pub_dt else ""
                            # Pinecone check for tenders older than start_dt
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
                                        logging.info(f"{self.source_type}: Encountered tender dated {publication_dt} older than start_date {start_date_str} and found in Pinecone. Stopping extraction.")
                                        break
                                    else:
                                        # Not in Pinecone, include but set initiation_date to start_dt
                                        init_date_str = start_dt.strftime("%Y-%m-%d")
                                        tender_data = {
                                            "name": name,
                                            "organization": org_name,
                                            "location": location,
                                            "submission_deadline": DateStandardizer.standardize_deadline(submission_deadline),
                                            "initiation_date": init_date_str,
                                            "details_url": detail_url,
                                            "content_type": "tender",
                                            "source_type": self.source_type,
                                        }
                                        try:
                                            t_obj = Tender(**tender_data)
                                            tenders.append(t_obj)
                                            logging.info(f"{self.source_type}: Encountered tender dated {publication_dt} older than start_date {start_date_str} but not found in Pinecone. Saving tender...")
                                        except Exception as te:
                                            logging.error(f"Error creating Tender object for {self.source_type} at URL: {detail_url}")
                                        continue  # Continue to next row
                                except Exception as e:
                                    logging.error(f"{self.source_type}: Error querying Pinecone when checking older tender: {e}")
                                    break

                            tender_data = {
                                "name": name,
                                "organization": org_name,
                                "location": location,
                                "submission_deadline": DateStandardizer.standardize_deadline(submission_deadline),
                                "initiation_date": init_date_str,
                                "details_url": detail_url,
                                "content_type": "tender",
                                "source_type": self.source_type,
                            }

                            try:
                                t_obj = Tender(**tender_data)
                                tenders.append(t_obj)
                                logging.info(f"Scraped URL for {self.source_type}: {detail_url}")
                            except Exception as te:
                                logging.error(f"Error creating Tender object for {self.source_type} at URL: {detail_url}")
                        except Exception as e:
                            logging.error(f"Error parsing listing item for {self.source_type}")
                            continue

                    pagination_section = await page.query_selector("section.pagination")
                    if not pagination_section:
                        break

                    next_btn = await pagination_section.query_selector(
                        "button:not([disabled]) span.mdc-button__label section:has-text('Następna')"
                    )
                    if next_btn:
                        await next_btn.click()
                        current_page += 1
                    else:
                        break

                metadata = ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=current_page
                )
                return {
                    "tenders": tenders,
                    "metadata": metadata
                }
            finally:
                await browser.close()

    async def extract_new_files_from_detail_page(
        self,
        context,
        details_url: str,
        threshold_date: datetime
    ) -> List[Tuple[bytes, str, Optional[str]]]:
        """
        Only extract newly added attachments from the tender detail page, i.e. attachments
        with a version date newer than 'threshold_date'.

        :param context: The Playwright browser context.
        :param details_url: The URL of the tender detail page.
        :param threshold_date: Only attachments in sections with a date > this value are downloaded.
        :return: A list of (file_content, filename, Optional[url]) tuples for newly added files.
        """
        processed_files = []
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        temp_dir = None
        page = None

        try:
            page = await context.new_page()
            await self._goto_with_retry(page, details_url, wait_until='networkidle', timeout=30000)
            logging.info(f"Opened page to extract new files: {details_url}")

            # Make a temporary directory for storing downloads before extraction
            temp_dir = Path(os.getcwd()) / "temp_bk_new_downloads"
            temp_dir.mkdir(exist_ok=True)
            logging.info(f"Temporary download directory created: {temp_dir}")

            # Find all <h2> headings for attachments: "Dodane do ogłoszenia w wersji X z dn. YYYY-MM-DD"
            headers = await page.query_selector_all("h2.attachements__header.mdc-typography--button")
            logging.info(f"Found {len(headers)} attachment section header(s) on the page.")

            for header in headers:
                header_text = (await header.inner_text()).strip()
                logging.info(f"Examining attachment section header: {header_text}")

                # Extract date using a regex search for "... z dn. YYYY-MM-DD"
                match = re.search(r"Z DN.\s+(\d{4}-\d{2}-\d{2})", header_text)
                if not match:
                    logging.warning(f"No date match found for header: '{header_text}' - skipping.")
                    continue

                section_date_str = match.group(1)
                try:
                    section_date = datetime.strptime(section_date_str, "%Y-%m-%d")
                except ValueError:
                    logging.warning(f"Failed to parse date '{section_date_str}' from header '{header_text}' - skipping.")
                    continue

                # Only download attachments if the date from this version is newer than threshold_date
                if section_date <= threshold_date:
                    logging.info(
                        f"Skipping older version block from {section_date_str} "
                        f"<= threshold_date {threshold_date.date()}"
                    )
                    continue

                # The <ol> right after this <h2> typically has the newly added attachments
                attachments_list_handle = await header.evaluate_handle(
                    """(h2) => {
                       // The next sibling might contain whitespace/text nodes;
                       // loop until we find an <ol> element with class 'attachements__list'.
                       let el = h2.nextElementSibling;
                       while (el) {
                         if (el.tagName === 'OL' && el.classList.contains('attachements__list')) {
                           return el;
                         }
                         el = el.nextElementSibling;
                       }
                       return null;
                    }"""
                )

                if not attachments_list_handle:
                    logging.warning(
                        f"No <ol.attachements__list> found immediately after header: '{header_text}'"
                    )
                    continue

                li_items = await attachments_list_handle.query_selector_all("li.attachements__download-item")
                logging.info(
                    f"Found {len(li_items)} attachment item(s) in this new version block dated {section_date_str}."
                )

                # Download each attachment item
                for li_item in li_items:
                    download_button = await li_item.query_selector("button.btn--pdf-dowload")
                    if not download_button:
                        logging.debug("No download button found in li_item—skipping.")
                        continue

                    # Initiate download
                    try:
                        async with page.expect_download(timeout=15000) as download_info:
                            await download_button.click()
                        download = await download_info.value

                        suggested_name = download.suggested_filename or "document"
                        temp_path = temp_dir / suggested_name
                        await download.save_as(str(temp_path))
                        logging.info(f"Downloaded file: {suggested_name} (temp: {temp_path})")

                        # Extract text from the downloaded file
                        file_results = await extraction_service.process_file_async(temp_path)
                        for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results:
                            processed_files.append((file_content, filename, details_url, preview_chars, original_bytes))
                            logging.info(f"Extracted content from file: {original_filename}")

                    except Exception as d_exc:
                        logging.error(
                            f"Download error in section '{header_text}': {d_exc}"
                        )

            # === Start BZP Budget Extraction Logic for new files ===
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
                                logging.info(f"{self.source_type}: Found BZP details in new file {out_name}: Plan={plan_num}, ID={plan_id}")
                                break
                except Exception as e:
                    logging.warning(f"{self.source_type}: Error decoding/searching new file {out_name} for BZP fields: {e}")

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
                        logging.info(f"{self.source_type}: Successfully scraped BZP budget row for update.")
                    else:
                        budget_info = (
                            f"---\n"
                            f"Nie znaleziono pozycji {plan_short_id} w planie {plan_num} na BZP.\n"
                            f"URL sprawdzony: https://ezamowienia.gov.pl/mo-client-board/bzp/tender-details/{urllib.parse.quote(plan_num, safe='')}\n"
                        )
                        logging.warning(f"{self.source_type}: BZP budget row not found for update with Plan={plan_num}, PosID={plan_short_id}")

                    processed_files.append((
                        budget_info.encode("utf-8"),
                        "bzp_budget.txt",
                        None,  # No direct URL for this derived file
                        budget_info[:200],
                        budget_info.encode("utf-8")
                    ))
                except Exception as e:
                    logging.error(f"{self.source_type}: Error during BZP budget scraping for update: {e}")
                    processed_files.append((
                    f"Error scraping BZP budget: {e}".encode("utf-8"),
                    "bzp_budget_error.txt",
                     None,
                    f"Error scraping BZP budget: {e}"[:200],
                    None
                    ))

        except Exception as e:
            if "Timeout" in str(e):
                logging.error(f"Timeout extracting new files for {self.source_type} at URL: {details_url}")
            else:
                logging.error(f"Error extracting new files for {self.source_type} at URL: {details_url} => {e}")

        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
                logging.info(f"Cleaned up temporary directory: {temp_dir}")
            if page:
                await page.close()

        logging.info(f"Finished extracting new files for {details_url}. Found {len(processed_files)} file(s).")
        return processed_files

    async def find_updates(
        self,
        tenders_to_monitor: List[TenderAnalysisResult]
    ) -> Dict[str, List[Tuple[str, bytes, str, str]]]:
        """
        Check if each tender has been updated by comparing 'Data ostatniej zmiany'
        to the tender's created_at date. If updated, re-extract files and return them.
        
        :param date_str: (Optional) A reference date in 'YYYY-MM-DD' format (not strictly required, 
                         but shown here as part of the signature).
        :param tenders_to_monitor: List of TenderAnalysisResult objects to check for updates.
        :return: Dictionary of form { "tender_id_str": [(filename, file_content, file_url), ...], ... }
        """

        updates_found: Dict[str, List[Tuple[str, bytes, str, str]]] = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()

                for tender in tenders_to_monitor:
                    page = await context.new_page()
                    try:
                        # Navigate to the tender detail page
                        await self._goto_with_retry(page, tender.tender_url, wait_until='networkidle', timeout=30000)

                        # Locate the "Data ostatniej zmiany" value on the page
                        change_date_el = await page.query_selector(
                            "div.field-with-label.announcement--date:has(p.label:has-text('Data ostatniej zmiany')) p.text"
                        )

                        if change_date_el:
                            change_date_str = (await change_date_el.inner_text()).strip()

                            # Attempt to parse the date (the example uses YYYY-MM-DD)
                            change_dt = None
                            for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                                try:
                                    change_dt = datetime.strptime(change_date_str, fmt)
                                    break
                                except ValueError:
                                    continue

                            if change_dt:

                                threshold_date = tender.updated_at or tender.created_at
                                if change_dt > threshold_date:
                                    # A more recent change has been found, so re-extract files
                                    logging.info(
                                        f"Tender {tender.id} changed on {change_date_str} "
                                        f"(created at {tender.created_at}), extracting files..."
                                    )

                                    extracted_files = await self.extract_new_files_from_detail_page(context, tender.tender_url, threshold_date)
                                    # extracted_files is List[Tuple[bytes, str, Optional[str]]]
                                    # print(extracted_files)
                                    # Store in the expected format (filename, file_content)
                                    updates_found[str(tender.id)] = [
                                        (file_content, filename, url, preview_chars, original_bytes)
                                        for (file_content, filename, url, preview_chars, original_bytes) in extracted_files
                                    ]
                            else:
                                logging.info(
                                    f"No newer change found for tender {tender.id}. "
                                    f"Data ostatniej zmiany: {change_date_str}, created_at: {tender.created_at}"
                                )
                        else:
                            logging.info(
                                f"'Data ostatniej zmiany' not found for tender {tender.id} at URL: {tender.tender_url}"
                            )

                    except Exception as exc:
                        logging.error(
                            f"Error checking updates for tender {tender.id} at {tender.tender_url}: {exc}"
                        )
                    finally:
                        await page.close()

            finally:
                await browser.close()

        return updates_found
