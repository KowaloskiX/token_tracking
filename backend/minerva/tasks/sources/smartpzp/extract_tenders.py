import logging
import asyncio
import os
import re
from datetime import datetime, time
from pathlib import Path
import shutil
import tempfile
from typing import Dict, List, Tuple, Optional
from uuid import uuid4
import urllib.parse

from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from minerva.core.utils.date_standardizer import DateStandardizer
from playwright.async_api import async_playwright, BrowserContext, Page
from bs4 import BeautifulSoup

# Adjust these imports to your actual project structure
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender
from minerva.core.services.vectorstore.file_content_extract.base import ExtractorRegistry
# Import helper functions for BZP
from minerva.tasks.sources.helpers import extract_bzp_plan_fields, scrape_bzp_budget_row

class SmartPZPTenderExtractor:
    def __init__(self, source_type: str = "smartpzp"):
        """
        Initialize the extractor without organization-specific configuration.
        """
        self.source_type = source_type
        self.base_url = "https://portal.smartpzp.pl/public/lista_przetargow/"

    async def scrape_detail_page(self, context: BrowserContext, final_url: str) -> dict:
        """
        Open a detail page in a new tab and extract additional fields.
        Returns a dict with keys: requirements, evaluation_criteria, location.
        """
        detail_info = {
            "requirements": "",
            "evaluation_criteria": "",
            "location": ""
        }
        detail_page = await context.new_page()
        try:
            await detail_page.goto(final_url, wait_until="networkidle", timeout=30000)
            await detail_page.wait_for_timeout(1000)

            page_html = await detail_page.content()
            soup = BeautifulSoup(page_html, "html.parser")

            # Extract requirements
            requirements_panels = soup.select(".panel-body .pzp-form")
            req_texts = []
            for panel in requirements_panels:
                title_el = panel.select_one(".title")
                desc_el = panel.select_one(".description")
                if title_el and desc_el:
                    title = title_el.get_text(strip=True)
                    desc = desc_el.get_text(strip=True)
                    req_texts.append(f"{title}:\n{desc}")
            detail_info["requirements"] = "\n\n".join(req_texts)

            # Extract evaluation criteria
            criteria_panels = soup.select(".panel-body .criteria")
            crit_texts = []
            for panel in criteria_panels:
                title_el = panel.select_one(".criteria-title")
                value_el = panel.select_one(".criteria-value")
                if title_el and value_el:
                    crit_title = title_el.get_text(strip=True)
                    crit_val = value_el.get_text(strip=True)
                    crit_texts.append(f"{crit_title}: {crit_val}")
            detail_info["evaluation_criteria"] = "\n\n".join(crit_texts)

            # Extract location
            location_el = soup.select_one("#postepowanieTabs\\:kartaPostepowaniaForm\\:dk_lokalizacja_uslugi")
            if location_el:
                detail_info["location"] = location_el.get_text(strip=True)

        except Exception as e:
            logging.error(f"Error scraping detail page {final_url}: {e}")
        finally:
            await detail_page.close()

        return detail_info

    async def ensure_table_sort(self, page: Page) -> bool:
        """
        Ensure the table is sorted by "Data wszczęcia" (descending).
        We do this whenever we come back from a detail page, for every page.
        """
        try:
            await page.wait_for_selector(
                "#listaPostepowanForm\\:postepowaniaTabela_data",
                state="visible", 
                timeout=30000
            )
            await page.wait_for_timeout(2000)

            headers = page.locator("th.ui-sortable-column:has-text('Data wszczęcia')")
            count = await headers.count()
            if count == 0:
                logging.error("No 'Data wszczęcia' header found.")
                return False

            logging.info(f"Found {count} matching 'Data wszczęcia' headers. Checking visibility...")
            visible_header = None
            for i in range(count):
                header_i = headers.nth(i)
                box = await header_i.bounding_box()
                if box and box["width"] > 0 and box["height"] > 0:
                    visible_header = header_i
                    logging.info(f"Using header index {i} with bounding box {box}")
                    break

            if not visible_header:
                logging.error("All 'Data wszczęcia' headers appear hidden.")
                return False

            await visible_header.scroll_into_view_if_needed()
            await visible_header.click()

            # Poll for up to 15s to confirm the table is sorted
            rows = await page.query_selector_all("#listaPostepowanForm\\:postepowaniaTabela_data tr")
            if len(rows) < 2:
                logging.error("Not enough rows to verify sort.")
                return False

            second_date_cell = await rows[1].query_selector("td:nth-child(5)")
            pre_click_date = await second_date_cell.inner_text() if second_date_cell else ""
            logging.info(f"Pre-click second row date was: {pre_click_date}")

            sorted_applied = False
            timeout = 15000
            interval = 500
            elapsed = 0

            while elapsed < timeout:
                rows = await page.query_selector_all("#listaPostepowanForm\\:postepowaniaTabela_data tr")
                if len(rows) >= 2:
                    first_cell = await rows[0].query_selector("td:nth-child(5)")
                    second_cell = await rows[1].query_selector("td:nth-child(5)")
                    first_date_text = await first_cell.inner_text() if first_cell else ""
                    second_date_text = await second_cell.inner_text() if second_cell else ""
                    if second_date_text != pre_click_date and first_date_text and second_date_text:
                        try:
                            first_dt = datetime.strptime(first_date_text, "%d-%m-%Y %H:%M")
                            second_dt = datetime.strptime(second_date_text, "%d-%m-%Y %H:%M")
                            if first_dt > second_dt:
                                logging.info(
                                    f"Sort applied: first row date: {first_date_text}, second row date: {second_date_text}"
                                )
                                sorted_applied = True
                                break
                        except Exception as e:
                            logging.error(f"Error parsing row dates: {e}")
                await page.wait_for_timeout(interval)
                elapsed += interval

            if not sorted_applied:
                logging.error("Sorting did not apply within 15s.")
            return sorted_applied

        except Exception as e:
            logging.error(f"Error ensuring sort: {e}")
            return False

    async def select_row(self, row: Page, page: Page):
        """
        Single-click the row, triggering rowSelect AJAX.
        """
        try:
            await row.click()
            await page.wait_for_timeout(1000)
        except Exception as e:
            logging.error(f"Error selecting row: {e}")

    async def click_podglad_button(self, page: Page):
        """
        Click the "Podgląd" button => triggers full nav to detail.
        """
        try:
            podglad_button = page.locator("#listaPostepowanForm\\:podgladPublicId")
            await podglad_button.wait_for(state="visible", timeout=10000)
            async with page.expect_navigation(wait_until="networkidle", timeout=30000):
                await podglad_button.click()
        except Exception as e:
            logging.error(f"Error clicking 'Podgląd' button: {e}")
            raise

    async def navigate_to_page(self, page: Page, current_pg: int, target_pg: int) -> bool:
        """
        Click next/prev until we reach 'target_pg' from 'current_pg'.
        Return True if success, or False if we can't proceed (disabled next/prev).
        """
        if target_pg == current_pg:
            return True
        elif target_pg > current_pg:
            for _ in range(current_pg, target_pg):
                next_button = page.locator("a.ui-paginator-next").first
                classes = await next_button.get_attribute("class")
                if classes and "ui-state-disabled" in classes:
                    logging.warning(f"Cannot go forward from page {current_pg}, next is disabled.")
                    return False
                logging.info(f"Forward: {current_pg} -> {current_pg+1}")
                await next_button.click()
                await page.wait_for_timeout(2000)
                current_pg += 1
            return True
        else:
            # If you want backward pagination, adapt similarly for .ui-paginator-prev
            # or just re-load page 1 and go forward
            logging.info(f"Going backward is not implemented, reloading listing might be an option.")
            return False
        

    async def execute(self, inputs: Dict) -> Dict:
        """
        Main extraction logic:
         1) Go to listing, handle cookies, do initial sort on page 1.
         2) For page in [1..max_pages]:
             - For each row:
               a) select row
               b) click 'Podgląd' => go detail
               c) parse detail => go back
               d) ALWAYS re-sort => table is consistent
               e) navigate from page1 back to pageN
               f) continue from next row
         3) Stop if tender older than start_date or run out of pages
        """
        max_pages = inputs.get("max_pages", 50)
        start_date_str = inputs.get("start_date")
        tender_names_index_name = inputs.get('tender_names_index_name', "tenders")
        embedding_model = inputs.get('embedding_model', "text-embedding-3-large")
        start_dt: Optional[datetime] = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                logging.info(f"Starting extraction with start_date: {start_date_str}")
            except ValueError:
                logging.error(f"Invalid date format for start_date: {start_date_str}")
        else:
            logging.info("Starting extraction with no start_date.")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            logging.info(f"Navigating to {self.base_url}")
            await page.goto(self.base_url, wait_until="networkidle", timeout=30000)
            try:
                cookie_accept = await page.query_selector("#j_idt32\\:cookie-acpt")
                if cookie_accept:
                    await cookie_accept.click()
                    await page.wait_for_timeout(1000)
            except Exception as e:
                logging.warning(f"Cookie dialog error: {e}")

            # sort page 1 initially
            if not await self.ensure_table_sort(page):
                logging.warning("Could not ensure proper sort order on first page")

            tenders: List[Tender] = []
            current_page = 1
            stop_pagination = False

            while current_page <= max_pages and not stop_pagination:
                logging.info(f"Processing page {current_page}")
                await page.wait_for_selector("#listaPostepowanForm\\:postepowaniaTabela_data", timeout=30000)
                rows = await page.query_selector_all("#listaPostepowanForm\\:postepowaniaTabela_data tr")
                if not rows:
                    logging.info("No rows found on this page. Stopping.")
                    break
                logging.info(f"Found {len(rows)} rows on page {current_page}")

                i = 0
                while i < len(rows):
                    rows = await page.query_selector_all("#listaPostepowanForm\\:postepowaniaTabela_data tr")
                    if i >= len(rows):
                        break
                    row = rows[i]
                    cells = await row.query_selector_all("td")
                    if len(cells) < 8:
                        i += 1
                        continue

                    tender_number = (await cells[0].inner_text()).strip()
                    name = (await cells[1].inner_text()).strip()
                    submission_deadline = (await cells[3].inner_text()).strip()
                    initiation_date = (await cells[4].inner_text()).strip()
                    status = (await cells[6].inner_text()).strip()
                    organization = (await cells[7].inner_text()).strip() if len(cells) > 7 else ""

                    if status == "W trakcie oceny ofert":
                        logging.info(f"Skipping tender '{name}' (status: {status})")
                        i += 1
                        continue

                    logging.info(f"Processing tender: {name}")

                    # row -> detail
                    await self.select_row(row, page)
                    try:
                        await self.click_podglad_button(page)
                    except Exception as e:
                        logging.error(f"Could not open detail for {name}: {e}")
                        i += 1
                        continue

                    detail_url = page.url
                    logging.info(f"Detail URL: {detail_url}")
                    detail_info = await self.scrape_detail_page(context, detail_url)

                    # Pinecone check for tenders older than start_dt
                    try:
                        final_pub_dt = None
                        if initiation_date:
                            try:
                                final_pub_dt = datetime.strptime(initiation_date, "%d-%m-%Y %H:%M")
                            except Exception as e:
                                logging.warning(f"Could not parse initiation date {initiation_date}: {e}")
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
                                    logging.info(f"{self.source_type}: Encountered tender dated {initiation_date} older than start_date {start_date_str} and found in Pinecone. Stopping extraction.")
                                    await page.go_back(wait_until="networkidle", timeout=30000)
                                    await page.wait_for_timeout(1000)
                                    stop_pagination = True
                                    break
                                else:
                                    # Not in Pinecone, include but set initiation_date to start_dt
                                    init_date_str = start_dt.strftime("%Y-%m-%d")
                                    tender_data = {
                                        "name": name,
                                        "organization": organization,
                                        "location": detail_info.get("location", ""),
                                        "submission_deadline": DateStandardizer.standardize_deadline(submission_deadline),
                                        "initiation_date": init_date_str,
                                        "details_url": detail_url,
                                        "content_type": "tender",
                                        "source_type": self.source_type,
                                        "requirements": detail_info.get("requirements", ""),
                                        "evaluation_criteria": detail_info.get("evaluation_criteria", "")
                                    }
                                    try:
                                        t_obj = Tender(**tender_data)
                                        tenders.append(t_obj)
                                        logging.info(f"{self.source_type}: Encountered tender dated {initiation_date} older than start_date {start_date_str} but not found in Pinecone. Saving tender...")
                                    except Exception as te:
                                        logging.error(f"Error creating Tender object for {self.source_type} at URL: {detail_url}")
                                    await page.go_back(wait_until="networkidle", timeout=30000)
                                    await page.wait_for_timeout(1000)
                                    i += 1
                                    continue  # Continue to next row
                            except Exception as e:
                                logging.error(f"{self.source_type}: Error querying Pinecone when checking older tender: {e}")
                                await page.go_back(wait_until="networkidle", timeout=30000)
                                await page.wait_for_timeout(1000)
                                stop_pagination = True
                                break
                    except Exception as e:
                        logging.warning(f"Error in Pinecone check logic: {e}")

                    sub_deadline = DateStandardizer.standardize_deadline(submission_deadline)
                    dt_initiation = ""
                    try:
                        dt_initiation = datetime.strptime(initiation_date, "%d-%m-%Y %H:%M").strftime("%Y-%m-%d")
                    except:
                        pass

                    tender_obj_data = {
                        "name": name,
                        "organization": organization,
                        "location": detail_info.get("location", ""),
                        "submission_deadline": sub_deadline,
                        "initiation_date": dt_initiation,
                        "details_url": detail_url,
                        "content_type": "tender",
                        "source_type": self.source_type,
                        "requirements": detail_info.get("requirements", ""),
                        "evaluation_criteria": detail_info.get("evaluation_criteria", "")
                    }
                    try:
                        t_obj = Tender(**tender_obj_data)
                        tenders.append(t_obj)
                        logging.info(f"Added tender: {t_obj.name}")
                    except Exception as e:
                        logging.error(f"Error creating Tender object for {name}: {e}")

                    # go back
                    await page.go_back(wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(1000)

                    # RE-SORT for *every* page after returning
                    # (Previously was if current_page == 1, but now we do it always)
                    if not await self.ensure_table_sort(page):
                        logging.warning("Could not reapply sort after returning from detail.")
                    await page.wait_for_timeout(2000)

                    # The site typically resets to page 1 after go_back, so we re-navigate
                    # from page1 => current_page
                    if current_page > 1:
                        success = await self.navigate_to_page(page, 1, current_page)
                        if not success:
                            logging.warning(f"Could not get back to page {current_page}, stopping.")
                            stop_pagination = True
                            break

                    i += 1
                    if stop_pagination:
                        break

                if stop_pagination:
                    break

                # Next page
                next_button = page.locator("a.ui-paginator-next").first
                try:
                    await next_button.wait_for(state="visible", timeout=10000)
                except:
                    logging.info("Next button not found. Ending pagination.")
                    break

                classes = await next_button.get_attribute("class")
                if classes and "ui-state-disabled" in classes:
                    logging.info("Next page button is disabled. No more pages.")
                    break

                logging.info(f"Navigating from page {current_page} to {current_page+1} ...")
                await next_button.click()
                await page.wait_for_timeout(2000)
                current_page += 1

            await page.close()
            await context.close()
            await browser.close()

            metadata = ExtractorMetadata(total_tenders=len(tenders), pages_scraped=current_page)
            return {
                "tenders": tenders,
                "metadata": metadata
            }

    async def extract_files_from_detail_page(
        self, context: BrowserContext, details_url: str
    ) -> List[Tuple[bytes, str, str]]:
        """
        Extract both the text content and downloadable files from the tender detail page.
        Returns a list of (file_content, filename, source_url).
        """
        page = await context.new_page()
        processed_files: List[Tuple[bytes, str, str]] = []
        unique_id = str(uuid4())
        temp_dir_path = Path(os.getcwd()) / "temp_downloads" / unique_id
        temp_dir_path.mkdir(parents=True, exist_ok=True)

        
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()

        try:
            logging.info(f"Accessing detail page for files: {details_url}")
            await page.goto(details_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_selector(
                "#postepowanieTabs\\:kartaPostepowaniaForm\\:wyk_karta_pos_nr",
                timeout=30000
            )

            # -- Extract standard textual details from the page (as before) --
            page_html = await page.content()
            soup = BeautifulSoup(page_html, "html.parser")

            number_el = soup.select_one("#postepowanieTabs\\:kartaPostepowaniaForm\\:wyk_karta_pos_nr")
            tender_number = number_el.get_text(strip=True) if number_el else ""
            name_el = soup.select_one("#postepowanieTabs\\:kartaPostepowaniaForm\\:wyk_karta_pos_nazwa")
            tender_name = name_el.get_text(strip=True) if name_el else ""
            short_desc_el = soup.select_one(
                "#postepowanieTabs\\:kartaPostepowaniaForm\\:wyk_karta_pos_skrocony_opis"
            )
            tender_short_desc = short_desc_el.get_text(strip=True) if short_desc_el else ""
            warunki_panel = soup.select_one("#postepowanieTabs\\:kartaPostepowaniaForm\\:warynkiUdzialuOutputPanel")
            warunki_text = warunki_panel.get_text(strip=True, separator="\n") if warunki_panel else ""
            kryteria_panel = soup.select_one("#postepowanieTabs\\:kartaPostepowaniaForm\\:j_idt565")
            kryteria_text = kryteria_panel.get_text(strip=True, separator="\n") if kryteria_panel else ""
            location_el = soup.select_one("#postepowanieTabs\\:kartaPostepowaniaForm\\:dk_lokalizacja_uslugi")
            location_text = location_el.get_text(strip=True) if location_el else ""

            extracted_text = (
                f"Numer postępowania: {tender_number}\n\n"
                f"Nazwa postępowania: {tender_name}\n\n"
                f"Skrócony opis zamówienia:\n{tender_short_desc}\n\n"
                f"Warunki udziału:\n{warunki_text}\n\n"
                f"Kryteria oceny ofert:\n{kryteria_text}\n\n"
                f"Lokalizacja usługi/Miejsce realizacji zamówienia:\n{location_text}\n"
            )
            page_content_bytes = extracted_text.encode("utf-8")
            processed_files.append((page_content_bytes, f"{tender_number}_details.txt", details_url, extracted_text[:250], page_content_bytes))

            # -- If there's a cookie dialog, accept it --
            try:
                cookie_accept = await page.query_selector("#j_idt32\\:cookie-acpt")
                if cookie_accept:
                    await cookie_accept.click()
                    await page.wait_for_timeout(1000)
            except Exception as e:
                logging.warning(f"Cookie dialog error: {e}")

            # -- Switch to "Dokumentacja" tab --
            await page.evaluate("""
                const tabLink = document.querySelector('a[href="#postepowanieTabs\\\\:dp"]');
                if (tabLink) {
                    tabLink.click();
                    const panel = document.querySelector('#postepowanieTabs\\\\:dp');
                    if (panel) {
                        panel.style.display = 'block';
                        panel.setAttribute('aria-hidden', 'false');
                    }
                }
            """)
            await page.wait_for_selector('#postepowanieTabs\\:dp[style*="display: block"]', timeout=10000)
            await page.wait_for_selector(
                "#postepowanieTabs\\:listaDokumentowForm\\:listaDokumentowTabela_data",
                state="visible",
                timeout=30000
            )
            await page.wait_for_timeout(2000)

            # -- PAGINATION LOOP for the "Dokumentacja" table --
            page_number = 1
            while True:
                logging.info(f"Processing Dokumentacja table page {page_number} ...")

                rows = await page.query_selector_all(
                    "#postepowanieTabs\\:listaDokumentowForm\\:listaDokumentowTabela_data > tr"
                )
                if not rows:
                    logging.info("No document rows found on this page.")
                    break

                logging.info(f"Found {len(rows)} document rows on page {page_number}")

                # -- Process document rows on the current page --
                for row in rows:
                    try:
                        empty_message = await row.query_selector("td.ui-datatable-empty-message")
                        if empty_message:
                            logging.info("Empty document table message found, skipping row.")
                            continue

                        name_cell = await row.query_selector("td:nth-child(2) span")
                        if not name_cell:
                            logging.warning("No document name found in row, skipping.")
                            continue

                        # Get inline style of the span:
                        span_style = await name_cell.get_attribute("style") or ""

                        # If this attachment is crossed out => skip
                        if "line-through" in span_style:
                            crossed_out_name = (await name_cell.inner_text()).strip()
                            logging.info(f"Skipping crossed-out attachment: {crossed_out_name}")
                            continue


                        doc_name = (await name_cell.inner_text()).strip()
                        logging.info(f"Processing document: {doc_name}")

                        checkbox = await row.query_selector('td.ui-selection-column .ui-chkbox-box')
                        if not checkbox:
                            logging.warning("Checkbox not found in this row, skipping.")
                            continue

                        # Select this row's checkbox
                        await checkbox.click()
                        await page.wait_for_timeout(500)

                        download_btn = await page.query_selector('#postepowanieTabs\\:listaDokumentowForm\\:downloadBtn')
                        if not download_btn:
                            logging.warning("Download button not found. Unchecking checkbox and skipping.")
                            await checkbox.click()
                            continue

                        try:
                            async with page.expect_download(timeout=30000) as download_info:
                                await download_btn.click()
                            download = await download_info.value

                            # Some documents trigger an additional "Yes" confirmation
                            try:
                                yes_btn = await page.wait_for_selector(
                                    '#postepowanieTabs\\:listaDokumentowForm\\:buttonYes',
                                    state="visible",
                                    timeout=1500
                                )
                                if yes_btn:
                                    async with page.expect_download(timeout=30000) as old_download_info:
                                        await yes_btn.click()
                                    download = await old_download_info.value
                            except Exception:
                                pass

                            suggested_name = download.suggested_filename or doc_name
                            temp_path = temp_dir_path / suggested_name

                            await download.save_as(str(temp_path))

                            logging.info(f"Downloaded file: {suggested_name}")

                            file_results = await extraction_service.process_file_async(temp_path)
                            if not file_results:
                                logging.warning(f"Extraction service returned no results for file '{suggested_name}'.")
                            else:
                                for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results:
                                    processed_files.append((file_content, filename, details_url, preview_chars, original_bytes))
                                
                        except Exception as e:
                            logging.error(f"Error downloading file {doc_name}: {e}")
                        finally:
                            # Uncheck the checkbox so we don't accidentally download it again
                            await checkbox.click()

                    except Exception as e:
                        logging.error(f"Error processing document row: {e}")
                        continue

                # -- Check if there's a "Next Page" button (not disabled) --
                next_btn = page.locator(
                    "#postepowanieTabs\\:listaDokumentowForm\\:listaDokumentowTabela_paginator_bottom "
                    "a.ui-paginator-next"
                )
                # You could also try the "_top" paginator if the site uses that instead, or both:
                # next_btn = page.locator("a.ui-paginator-next").first

                # If the next button is missing or disabled, break the loop
                try:
                    classes = await next_btn.get_attribute("class")
                except:
                    # No next button at all
                    logging.info("No Next button found for documents. Ending doc pagination.")
                    break

                if not classes or "ui-state-disabled" in classes:
                    logging.info("Next button is disabled or not found. No more doc pages.")
                    break

                # Otherwise, go to the next page
                page_number += 1
                logging.info(f"Going to documents page {page_number} ...")
                await next_btn.click()
                # Give the page time to load next set of documents
                await page.wait_for_timeout(2000)
                # Ensure the new page is actually loaded (in practice, you might also wait for a specific selector to update)
                await page.wait_for_selector(
                    "#postepowanieTabs\\:listaDokumentowForm\\:listaDokumentowTabela_data",
                    timeout=30000
                )

            # === Start BZP Budget Extraction Logic ===
            plan_num, plan_id = None, None
            pdf_extractor = ExtractorRegistry().get('.pdf')
            for content, out_name, url, preview, original_bytes in processed_files:
                try:
                    if out_name.lower().endswith(".pdf"):
                        temp_pdf_path = temp_dir_path / out_name
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

            logging.info(f"Successfully processed {len(processed_files)} files from {details_url}")

        except Exception as e:
            logging.error(f"Error accessing detail page for files {details_url}: {e}")
        finally:
            if temp_dir_path.exists():
                shutil.rmtree(temp_dir_path)
            await page.close()

        return processed_files
    

    async def _extract_new_attachments_from_detail_page(
        self, context: BrowserContext, details_url: str, last_date: datetime
    ) -> List[Tuple[str, bytes, str]]:
        """
        Similar logic to 'extract_files_from_detail_page' but:
         - DOES NOT create or return any textual .txt files.
         - Extracts the date of each attachment from the table and compares
           it to 'last_date'.
         - Only downloads files whose upload date > last_date.
         - Returns a list of tuples: (filename, file_content, file_url).
        """
        page = await context.new_page()
        new_files: List[Tuple[str, bytes, str]] = []
        temp_dir_path = Path(tempfile.mkdtemp())

        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()

        try:
            logging.info(f"Accessing detail page for potential updates: {details_url}")
            await page.goto(details_url, wait_until="networkidle", timeout=30000)
            # Wait for a known element to ensure the detail page is loaded
            await page.wait_for_selector(
                "#postepowanieTabs\\:kartaPostepowaniaForm\\:wyk_karta_pos_nr",
                timeout=30000
            )

            # Accept cookie if present
            try:
                cookie_accept = await page.query_selector("#j_idt32\\:cookie-acpt")
                if cookie_accept:
                    await cookie_accept.click()
                    await page.wait_for_timeout(1000)
            except Exception as e:
                logging.warning(f"Cookie dialog error (ignored): {e}")

            # Switch to "Dokumentacja" tab (same approach as in extract_files_from_detail_page)
            await page.evaluate("""
                const tabLink = document.querySelector('a[href="#postepowanieTabs\\\\:dp"]');
                if (tabLink) {
                    tabLink.click();
                    const panel = document.querySelector('#postepowanieTabs\\\\:dp');
                    if (panel) {
                        panel.style.display = 'block';
                        panel.setAttribute('aria-hidden', 'false');
                    }
                }
            """)
            await page.wait_for_selector('#postepowanieTabs\\:dp[style*="display: block"]', timeout=10000)
            await page.wait_for_selector(
                "#postepowanieTabs\\:listaDokumentowForm\\:listaDokumentowTabela_data",
                state="visible",
                timeout=30000
            )
            await page.wait_for_timeout(2000)

            page_number = 1
            while True:
                logging.info(f"[Updates] Checking Dokumentacja table on page {page_number} ...")
                rows = await page.query_selector_all(
                    "#postepowanieTabs\\:listaDokumentowForm\\:listaDokumentowTabela_data > tr"
                )
                if not rows:
                    logging.info("[Updates] No document rows found on this page.")
                    break

                for row in rows:
                    try:
                        # Check for "No records" or empty row
                        empty_message = await row.query_selector("td.ui-datatable-empty-message")
                        if empty_message:
                            logging.info("[Updates] Empty documents table, skipping.")
                            continue

                        cells = await row.query_selector_all("td")
                        if len(cells) < 4:
                            continue  # Not enough columns => skip

                        # doc_name is in 2nd column (like original code):
                        name_cell = cells[1]
                        doc_name = (await name_cell.inner_text()).strip()

                        doc_name_span = await name_cell.query_selector("span")
                        if not doc_name_span:
                            continue

                        span_style = await doc_name_span.get_attribute("style") or ""

                        # Skip if style has "line-through"
                        if "line-through" in span_style:
                            crossed_out_name = (await doc_name_span.inner_text()).strip()
                            logging.info(f"[Updates] Skipping crossed-out attachment: {crossed_out_name}")
                            continue

                        # doc_date might be in (for example) 4th column. 
                        # Adjust the index as needed for your site:
                        date_cell = cells[2]
                        doc_date_text = (await date_cell.inner_text()).strip()
                        if not doc_date_text:
                            # If we can't read date, skip or assume no date => skip
                            logging.warning(f"[Updates] Could not read date for doc '{doc_name}'. Skipping.")
                            continue

                        # Attempt to parse date (assuming format "dd-mm-YYYY HH:MM")
                        try:
                            doc_dt = datetime.strptime(doc_date_text, "%d-%m-%Y %H:%M")
                        except Exception as e:
                            logging.warning(
                                f"[Updates] Could not parse date '{doc_date_text}' for '{doc_name}': {e}"
                            )
                            continue

                        # Compare with last_date
                        if doc_dt <= last_date:
                            logging.debug(
                                f"[Updates] Document '{doc_name}' date={doc_dt} <= last_date={last_date}, skip download."
                            )
                            continue

                        # If we got here => doc_dt > last_date => we download
                        logging.info(f"[Updates] Document '{doc_name}' is NEW (date={doc_date_text}). Downloading...")
                        checkbox = await row.query_selector('td.ui-selection-column .ui-chkbox-box')
                        if not checkbox:
                            logging.warning(
                                "[Updates] Could not find checkbox for row => cannot download."
                            )
                            continue

                        await checkbox.click()
                        await page.wait_for_timeout(500)

                        download_btn = await page.query_selector('#postepowanieTabs\\:listaDokumentowForm\\:downloadBtn')
                        if not download_btn:
                            logging.warning("[Updates] Download button not found. Unchecking and skipping.")
                            await checkbox.click()
                            continue

                        try:
                            async with page.expect_download(timeout=30000) as download_info:
                                await download_btn.click()
                            download = await download_info.value

                            # Some documents trigger an additional "Yes" confirmation
                            try:
                                yes_btn = await page.wait_for_selector(
                                    '#postepowanieTabs\\:listaDokumentowForm\\:buttonYes',
                                    state="visible",
                                    timeout=1500
                                )
                                if yes_btn:
                                    async with page.expect_download(timeout=30000) as second_download_info:
                                        await yes_btn.click()
                                    download = await second_download_info.value
                            except Exception:
                                pass

                            suggested_name = download.suggested_filename or doc_name
                            temp_path = temp_dir_path / suggested_name
                            await download.save_as(str(temp_path))

                            logging.info(f"[Updates] Downloaded new file: {suggested_name}")

                            file_results = await extraction_service.process_file_async(temp_path)
                            if not file_results:
                                logging.warning(f"Extraction service returned no results for file '{suggested_name}'.")
                            else:
                                for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results:
                                    new_files.append((file_content, filename, details_url, preview_chars, original_bytes))

                        except Exception as e:
                            logging.error(f"[Updates] Error downloading file '{doc_name}': {e}")
                        finally:
                            # Uncheck the checkbox
                            await checkbox.click()

                    except Exception as e:
                        logging.error(f"[Updates] Error processing row: {e}")
                        continue

                # Move to next page if possible
                next_btn = page.locator(
                    "#postepowanieTabs\\:listaDokumentowForm\\:listaDokumentowTabela_paginator_bottom "
                    "a.ui-paginator-next"
                )
                try:
                    classes = await next_btn.get_attribute("class")
                except:
                    logging.info("[Updates] No next button found => end of doc pages.")
                    break

                if not classes or "ui-state-disabled" in classes:
                    logging.info("[Updates] Next doc-page button is disabled => end of doc pages.")
                    break

                page_number += 1
                logging.info(f"[Updates] Going to documents table page {page_number} ...")
                await next_btn.click()
                await page.wait_for_timeout(2000)
                await page.wait_for_selector(
                    "#postepowanieTabs\\:listaDokumentowForm\\:listaDokumentowTabela_data",
                    timeout=30000
                )

        except Exception as e:
            logging.error(f"[Updates] Error accessing detail page {details_url} for new attachments: {e}")
        finally:
            if temp_dir_path.exists():
                shutil.rmtree(temp_dir_path)
            await page.close()

        return new_files

    # ------------------------------------------------------
    # NEW METHOD: find_updates
    # ------------------------------------------------------
    async def find_updates(
        self,
        tenders_to_monitor: List["TenderAnalysisResult"],  # type: ignore
    ) -> Dict[str, List[Tuple[str, bytes, str]]]:
        """
        For each tender in 'tenders_to_monitor', checks if there are any NEW attachments
        (comparing each attachment's upload date to the tender's last_updated_at or created_at).
        Downloads and returns them as:

            {
              "tender_id_as_string": [(filename, file_content, file_url), ...],
              ...
            }
        """
        updates_found: Dict[str, List[Tuple[str, bytes, str]]] = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            for tender in tenders_to_monitor:
                if not tender.tender_url:
                    continue
                # Determine the reference date: updated_at or created_at
                last_date = tender.updated_at or tender.created_at
                if not last_date:
                    # In theory created_at is always present, but just in case
                    logging.warning(f"No valid date found for tender {tender.id}, skipping.")
                    continue

                details_url = tender.tender_url
                logging.info(f"[Updates] Checking {details_url} for new attachments since {last_date} ...")

                # Extract new attachments from the detail page
                new_attachments = await self._extract_new_attachments_from_detail_page(context, details_url, last_date)

                if new_attachments:
                    updates_found[str(tender.id)] = new_attachments
                    logging.info(f"[Updates] Found {len(new_attachments)} new attachments for tender {tender.id}")

            await context.close()
            await browser.close()

        return updates_found