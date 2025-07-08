import logging
import os
from pathlib import Path
import pprint
import re
import shutil
from uuid import uuid4
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple
import asyncio
import random
import httpx
from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from minerva.core.services.ai_pick_main_doc import ai_pick_main_doc
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from playwright.async_api import async_playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from minerva.core.utils.date_standardizer import DateStandardizer
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender
from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString
import urllib.parse
# Import helper functions for BZP
from minerva.tasks.sources.helpers import extract_bzp_plan_fields, scrape_bzp_budget_row

# Set logging to INFO for key events only.
logging.basicConfig(level=logging.INFO)

# Maximum retries for timeout errors
MAX_RETRIES = 3

class TenderExtractor:
    def __init__(self):
        self.base_url = "https://ezamowienia.gov.pl/mp-client/search/list/"
        self.api_url = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
        self.source_type = "ezamowienia"
        

    def _html_to_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator="\n")

    async def format_date(self, date_str: str) -> str:
        """Convert Polish date string to ISO format"""
        months_pl = {
            'stycznia': '01', 'lutego': '02', 'marca': '03', 'kwietnia': '04',
            'maja': '05', 'czerwca': '06', 'lipca': '07', 'sierpnia': '08',
            'września': '09', 'października': '10', 'listopada': '11', 'grudnia': '12'
        }
        date_parts = date_str.split(',')[0].strip().split()
        if len(date_parts) < 3:
            return date_str
        day = date_parts[0].zfill(2)
        month = months_pl.get(date_parts[1], '01')
        year = date_parts[2]
        return f"{year}-{month}-{day}"

    async def extract_files_from_detail_page(self, context, details_url: str) -> List[Tuple[bytes, str, str, Optional[str]]]:
        page = await context.new_page()
        processed_files = []
        extraction_service = FileExtractionService()
        unique_id = str(uuid4())
        temp_dir_path = Path(os.getcwd()) / "temp_downloads" / unique_id
        temp_dir_path.mkdir(parents=True, exist_ok=True)
        bzp_extracted = False
        plan_num, plan_id = None, None
        
        try:
            # Navigate to detail page with retry and increased timeout
            navigated = False
            for attempt in range(MAX_RETRIES):
                try:
                    await page.goto(details_url, wait_until='domcontentloaded', timeout=20000) # Increased timeout
                    navigated = True
                    break # Success
                except PlaywrightTimeoutError as e:
                    logging.warning(f"{self.source_type}: Detail page goto failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    if attempt + 1 == MAX_RETRIES:
                        logging.error(f"{self.source_type}: Failed to navigate to {details_url} after {MAX_RETRIES} attempts.")
                        # Cannot proceed without the page, clean up and return
                        if temp_dir_path.exists():
                            shutil.rmtree(temp_dir_path)
                        await page.close()
                        return [] 
                    await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # Wait for one of the main content selectors with retry
            success = False
            final_exception = None
            for attempt in range(MAX_RETRIES):
                try:
                    for selector in [
                        "mat-tab-group",
                        "app-search-engine-tender-documents",
                        "div.link-item",
                        "table"
                    ]:
                        try:
                            await page.wait_for_selector(selector, timeout=20000) # Increased timeout
                            success = True
                            break # Found one selector
                        except PlaywrightTimeoutError: 
                            continue # Try next selector
                    if success:
                        break # Exit retry loop if a selector was found
                    else:
                        raise PlaywrightTimeoutError(f"None of the main content selectors found on {details_url}")
                except PlaywrightTimeoutError as e:
                    final_exception = e
                    logging.warning(f"{self.source_type}: Wait for main content failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    if attempt + 1 == MAX_RETRIES:
                         logging.error(f"{self.source_type}: Could not detect main content selectors for {details_url} after {MAX_RETRIES} attempts.")
                         # Clean up and return empty if content not found
                         if temp_dir_path.exists():
                             shutil.rmtree(temp_dir_path)
                         await page.close()
                         return []
                    await asyncio.sleep(random.uniform(2.0, 4.0))

            await page.wait_for_timeout(2000)

            # Track how many documents we've processed
            announcement_count = 0
            document_count = 0
            budget_info = "" # Initialize budget_info
            # 1. Extract files from "Ogłoszenia i dokumenty postępowania utworzone w systemie"
            announcement_section = await page.query_selector("app-search-engine-tender-documents")
            if announcement_section:
                announcement_links = await announcement_section.query_selector_all("div.section h3 a")
                
                for link in announcement_links:
                    try:
                        link_text = await link.inner_text()
                        url = await link.get_attribute("href")
                        if not url:
                            continue
                        if url.startswith("/"):
                            url = f"https://ezamowienia.gov.pl{url}"
                        
                        # Open the announcement link in a new page with retry
                        announcement_page = await context.new_page()
                        try:
                            navigated_announcement = False
                            for attempt in range(MAX_RETRIES):
                                try:
                                    await announcement_page.goto(url, wait_until='domcontentloaded', timeout=30000) # Increased timeout
                                    navigated_announcement = True
                                    break # Success
                                except PlaywrightTimeoutError as e:
                                    logging.warning(f"{self.source_type}: Announcement page goto failed ({url}, attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                                    if attempt + 1 == MAX_RETRIES:
                                        logging.error(f"{self.source_type}: Failed to navigate to announcement {url} after {MAX_RETRIES} attempts.")
                                        # Continue to next link if this one fails
                                        raise e 
                                    await asyncio.sleep(random.uniform(2.0, 4.0))
                            
                            await announcement_page.wait_for_timeout(2000)
                            
                            # Get HTML for plan extraction, and extract main content as before
                            html_content = await announcement_page.content()
                            content_text = ""
                            
                            # Try various selectors for the main content
                            for content_selector in [".mat-card-content", ".main-content", "main", "body"]:
                                try:
                                    content_element = await announcement_page.query_selector(content_selector)
                                    if content_element:
                                        content_text = await content_element.inner_text()
                                        if len(content_text) > 200:
                                            break
                                except Exception:
                                    continue
                            
                            if not content_text or len(content_text) < 200:
                                content_text = self._html_to_text(html_content)

                            if not bzp_extracted:
                                logging.info(f"{self.source_type}: Attempting BZP extraction from announcement content...")
                                plan_num, plan_id = extract_bzp_plan_fields(content_text)
                                logging.info(f"{self.source_type}: BZP extraction result - plan_num: '{plan_num}', plan_id: '{plan_id}'")
                                
                                if plan_num and plan_id:
                                    bzp_extracted = True  # Mark as extracted to avoid duplicates
                                    # Plan ID might have extra details, try splitting if needed, but pass the original to the helper
                                    plan_short_id = plan_id.split()[0] if plan_id else plan_id # Helper expects the precise ID
                                    logging.info(f"{self.source_type}: Found BZP details in announcement text: Plan={plan_num}, ID={plan_id}. Attempting budget scrape.")
                                    try:
                                        budget_row_data = await scrape_bzp_budget_row(context, plan_num, plan_short_id)
                                        if budget_row_data:
                                            row_str, bzp_url = budget_row_data
                                            budget_info = (
                                                f"\n\n---\n"
                                                f"**Dane z planu postępowań BZP (z treści ogłoszenia)**\n"
                                                f"Przewidywany budżet/Orientacyjna wartość/cena zamówienia:\n{row_str}\n"
                                            )
                                            logging.info(f"{self.source_type}: Successfully scraped BZP budget row for Plan={plan_num}, PosID={plan_short_id}.")
                                        else:
                                             # Construct URL for logging even if row not found
                                            bzp_url_checked = f"https://ezamowienia.gov.pl/mo-client-board/bzp/tender-details/{urllib.parse.quote(plan_num, safe='')}"
                                            budget_info = (
                                                f"\n\n---\n"
                                                f"Nie znaleziono pozycji {plan_short_id} w planie {plan_num} na BZP.\n"
                                                f"URL sprawdzony: {bzp_url_checked}\n"
                                                f"---"
                                            )
                                            logging.warning(f"{self.source_type}: BZP budget row not found for Plan={plan_num}, PosID={plan_short_id}. URL: {bzp_url_checked}")
                                    except Exception as e_bzp:
                                        logging.error(f"{self.source_type}: Error during BZP budget scraping for Plan={plan_num}, PosID={plan_short_id}: {e_bzp}")
                                        budget_info = (
                                            f"\n\n---\n"
                                            f"Błąd podczas pobierania danych BZP dla planu {plan_num}, pozycji {plan_short_id}: {e_bzp}\n"
                                            f"---"
                                        )

                                    # Add budget info as a separate file (only once per tender)
                                    processed_files.append((
                                        budget_info.encode("utf-8"),
                                        "bzp_budget.txt",
                                        bzp_url if 'bzp_url' in locals() else None, # Use BZP URL if available
                                        budget_info[:200],
                                        None # No original_bytes for generated text
                                    ))
                                    logging.info(f"{self.source_type}: Added bzp_budget.txt for Plan={plan_num}, PosID={plan_short_id}")
                                    announcement_count += 1 # Count it as a processed file

                            # Save the announcement content as a text file
                            if len(content_text) > 50: # Reduced minimum size slightly
                                filename = f"{link_text.replace(' ', '_').replace('/', '-')}.txt"
                                preview_chars = content_text[:200] if len(content_text) > 200 else content_text
                                file_content_bytes = content_text.encode("utf-8")
                                
                                processed_files.append((
                                    file_content_bytes,
                                    filename,
                                    url,
                                    preview_chars,
                                    file_content_bytes # Added original_bytes
                                ))
                                announcement_count += 1
                            else:
                                logging.warning(f"{self.source_type}: Announcement content too small after processing: {len(content_text)} chars from {url}")
                        except Exception as e:
                            logging.error(f"{self.source_type}: Error processing announcement page {url}: {e}") # Log specific URL
                        finally:
                            await announcement_page.close()
                    except Exception as e:
                        logging.error(f"{self.source_type}: Error processing announcement link {link}: {e}") # Log link object might not be helpful, maybe url if available?
                        continue

            headers = await page.query_selector_all('h2')
            for header in headers:
                header_text = (await header.inner_text()).strip()
                if "Pozostałe dokumenty postępowania" in header_text:
                    header_handle = header
                    next_sibling = await header_handle.evaluate_handle('node => node.parentElement.nextElementSibling')
                    if next_sibling:
                        links = await next_sibling.query_selector_all('a')
                        for link in links:
                            href = await link.get_attribute('href')
                            if not href:
                                continue
                            if href.startswith("/"):
                                url = f"https://ezamowienia.gov.pl{href}"
                            else:
                                url = href
                            name = (await link.inner_text()).strip()
                            download_successful = False
                            try:
                                async with page.expect_download(timeout=30000) as download_info: # Increased timeout
                                    # Retry clicking the link
                                    click_success = False
                                    for attempt in range(MAX_RETRIES):
                                        try:
                                            await link.click()
                                            click_success = True
                                            break # Success
                                        except PlaywrightTimeoutError as click_e: # Catch specific click timeout if possible, else broader exception
                                            logging.warning(f"{self.source_type}: Download link click failed for '{name}' (attempt {attempt + 1}/{MAX_RETRIES}): {click_e}")
                                            if attempt + 1 == MAX_RETRIES:
                                                logging.error(f"{self.source_type}: Failed to click download link '{name}' after {MAX_RETRIES} attempts.")
                                                # Continue to next link
                                                break
                                            await asyncio.sleep(random.uniform(2.0, 4.0))
                                    
                                    if not click_success:
                                        continue # Skip this link if click failed repeatedly

                                    # If click was successful, wait for download 
                                    download = await download_info.value
                                    download_successful = True # Mark as successful if download object received
                                
                                # Process download outside the 'with' block if successful
                                file_name = download.suggested_filename or name
                                temp_file_path = temp_dir_path / file_name
                                await download.save_as(str(temp_file_path))
                                
                                if os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) > 100:
                                    file_results = await extraction_service.process_file_async(temp_file_path)
                                    for file_content, filename, preview_chars, original_bytes, original_filename in file_results:
                                        if len(file_content) > 100:
                                            processed_files.append((
                                                file_content, filename, url, preview_chars, original_bytes
                                            ))
                                            document_count += 1
                                else:
                                     # File might be empty or too small after download
                                    logging.warning(f"{self.source_type}: Downloaded file '{file_name}' is too small or does not exist at {temp_file_path}.")
                                    if os.path.exists(temp_file_path):
                                        os.remove(temp_file_path) # Clean up small/empty file
                                        
                            except PlaywrightTimeoutError as download_timeout_e:
                                # This catches timeout waiting for the download event itself
                                logging.error(f"{self.source_type}: Timeout waiting for download event for '{name}': {download_timeout_e}")
                            except Exception as e:
                                # Catch other errors during download expectation/processing
                                logging.error(f"{self.source_type}: Error processing download for file '{name}': {e}")
                                # Ensure cleanup if download failed mid-process
                                if not download_successful and 'download' in locals() and download:
                                     try:
                                         temp_file_path_on_error = temp_dir_path / (download.suggested_filename or name)
                                         if os.path.exists(temp_file_path_on_error):
                                              os.remove(temp_file_path_on_error)
                                     except Exception as cleanup_e:
                                         logging.error(f"{self.source_type}: Error cleaning up failed download artifact: {cleanup_e}")
                                continue # Move to the next link

            # Check if we processed any documents
            if announcement_count == 0 and document_count == 0:
                # logging.warning(f"{self.source_type}: No documents or announcements processed, trying to extract page content")
                try:
                    # Try to get the page title
                    title_element = await page.query_selector("h1")
                    title = await title_element.inner_text() if title_element else "Tender Details"
                    
                    # Get the full page HTML and convert to text
                    html_content = await page.content()
                    page_text = self._html_to_text(html_content)
                    
                    # Clean up the text and ensure we have meaningful content
                    page_text = '\n'.join(line for line in page_text.splitlines() if line.strip())
                    
                    if len(page_text) > 200:
                        page_content_bytes = f"Title: {title}\n\n{page_text}".encode("utf-8")
                        processed_files.append((
                            page_content_bytes,
                            "page_content.txt",
                            details_url,
                            page_text[:200],
                            page_content_bytes # Added original_bytes
                        ))
                        # logging.info(f"{self.source_type}: Extracted page content as fallback")
                    else:
                        # logging.error(f"{self.source_type}: Page content too small: {len(page_text)} chars")
                        pass
                except Exception as e:
                    logging.error(f"{self.source_type}: Error extracting fallback content: {e}")

            # logging.info(f"{self.source_type}: Successfully processed {len(processed_files)} files from {details_url} (Announcements: {announcement_count}, Documents: {document_count})")
            
        except Exception as e:
            logging.error(f"{self.source_type}: Error accessing detail page {details_url}: {e}")
        finally:
            if temp_dir_path.exists():
                shutil.rmtree(temp_dir_path)
            await page.close()
            
        return processed_files
    
    def _extract_subject_from_html(self, html: str) -> Optional[str]:
        """
        Build one merged line that contains, in order

            • "Krótki opis …" section text
            • Główny kod CPV
            • Dodatkowy kod CPV   (if present)

        Missing pieces are skipped.  Returns None if *nothing* was found.
        """
        soup = BeautifulSoup(html, "html.parser")

        # helper ────────────────────────────────────────────────────────────
        def grab(pattern: str) -> Optional[str]:
            """
            Find the first <h3> whose full visible text matches *pattern*
            (case-insensitive, ignores intermediate tags), then collect:

            • any text inside that same <h3> (e.g. <span> with the code)
            • every node up to the next <h3> (for multi-line descriptions)

            Returns the cleaned string or None.
            """
            header = soup.find(
                lambda tag: tag.name == "h3"
                and re.search(pattern, tag.get_text(" ", strip=True), re.I)
            )
            if not header:
                return None

            pieces: list[str] = []

            # text inside the header itself (covers CPV that lives in <span>)
            txt = header.get_text(" ", strip=True)
            # we want ONLY the part after the label ("Krótki opis" has none)
            # drop empty results (e.g. "Dodatkowy kod CPV:" with no inline code)
            if txt:
                pieces.append(txt)

            # walk forward until the next <h3>
            for node in header.next_siblings:
                if isinstance(node, Tag) and node.name == "h3":
                    break
                text = (
                    node.get_text(" ", strip=True)
                    if isinstance(node, Tag)
                    else node.strip()
                )
                if text:
                    pieces.append(text)

            return " ".join(pieces).strip() or None

        # collect each block
        subject       = grab(r"\bKrótki\s+opis\b")
        cpv_main      = grab(r"Gł[óo]wny\s+kod\s+CPV")      # ó or o just in case
        cpv_additional = grab(r"Dodatkowy\s+kod\s+CPV")

        # merge while skipping missing parts
        merged = " ".join(x for x in (subject, cpv_main, cpv_additional) if x).strip()
        return merged or None

    # -------------------------------------------
    # 3. Helper: async loader that re-uses the current browser context
    # -------------------------------------------

    def _scrape_sections_5_1_and_5_1_1(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")

        # ────────────────────────────────────────────── 5.1 (root only)
        def collect_5_1() -> str:
            anchor = soup.find(id=re.compile(r"^section5\.1_\d+$"))
            if anchor is None:
                return ""

            texts = []
            for el in anchor.parent.next_elements:
                # STOP as soon as we reach the first sub-section 5.1.1
                if isinstance(el, Tag) and el.get("id", "").startswith("section5.1.1_"):
                    break
                if isinstance(el, NavigableString):
                    t = el.strip()
                    if t:
                        texts.append(t)
            return " ".join(texts).strip()

        # ────────────────────────────────────────────── 5.1.1 (three fields)
        def collect_5_1_1() -> str:
            blk = soup.find(id=re.compile(r"^section5\.1\.1_\d+$"))
            if blk is None:
                return ""

            wanted = {
                "business-term|name|BT-23":  "Charakter zamówienia",
                "business-term|name|BT-262": "Główna klasyfikacja (cpv)",
                "business-term|name|BT-263": "Dodatkowa klasyfikacja (cpv)",
            }
            lines = []

            container = blk.find_parent("div", class_="subsection-content")
            for div in container.find_all("div", recursive=False):
                label = div.find("span", class_="label")
                if not label:
                    continue
                key = label.get("data-labels-key")
                if key not in wanted:
                    continue

                value = " ".join(
                    node.get_text(" ", strip=True) if isinstance(node, Tag) else node.strip()
                    for node in label.next_siblings
                    if (isinstance(node, NavigableString) and node.strip()) or
                    (isinstance(node, Tag) and node.get_text(strip=True))
                )
                lines.append(f"{wanted[key]} : {value}")

            return "\n".join(lines)

        part_5_1   = collect_5_1()
        part_5_1_1 = collect_5_1_1()

        return "\n\n".join(p for p in (part_5_1, part_5_1_1) if p) or None

    async def _fetch_tender_subject(self, context, detail_url: str) -> str | None:
        """Open the detail page, jump to the first announcement,
        and return the 'Krótki opis …' text."""
        detail_page = await context.new_page()
        try:
            # ── go to the detail list page ─────────────────────
            await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
            await detail_page.wait_for_selector("app-search-engine-tender-documents", timeout=15000)

            # find first announcement link (same selector you use in downloads)
            await detail_page.wait_for_timeout(2000)
            link = await detail_page.query_selector("app-search-engine-tender-documents div.section h3 a")

            if not link:
                logging.warning(f"No link: {link}")
                NOTICE_FRAG = "/mo-client-board/bzp/notice-details/"
                        # ──────────────────────────────────────────────────────────────────
                # existing code …
                link = await detail_page.query_selector(
                    "app-search-engine-tender-documents div.section h3 a")

                if not link:
                    # ------------------------------------------------------------------
                    # 1) wait up to 5 s for ANY anchor whose href contains the fragment
                    #    to appear in the DOM (outside or inside an iframe)
                    # ------------------------------------------------------------------
                    try:
                        link = await detail_page.wait_for_selector(
                            f'a[href*="{NOTICE_FRAG}"]',
                            timeout=5_000
                        )
                    except PlaywrightTimeoutError:
                        link = None

                    # ------------------------------------------------------------------
                    # 2) if the anchor is inside an  <iframe>  (rare but happens),
                    #    look through all child frames
                    # ------------------------------------------------------------------
                    if link is None:
                        for frame in detail_page.frames:
                            try:
                                link = await frame.query_selector(
                                    f'a[href*="{NOTICE_FRAG}"]')
                                if link:
                                    break
                            except Exception:
                                pass   # ignore inaccessible frames

                    # ------------------------------------------------------------------
                    # 3) still nothing?  fall back to full-HTML regex scan as before
                    # ------------------------------------------------------------------
                    if link is None:
                        raw_html = await detail_page.content()
                        soup = BeautifulSoup(raw_html, "lxml")
                        tag = soup.select_one(f'a[href*="{NOTICE_FRAG}"]') \
                            or soup.find(
                                "a",
                                string=re.compile(r"\d{4}/S\s+\d{3}-\d{5,}")
                            )
                        if tag:
                            href = tag["href"]
                        else:
                            logging.warning(
                                f"{self.source_type}: no EU-notice link on {detail_url} FALLBACK TO FILE UPLOAD"
                            )
                            

                            # FALLBACK TO FILE UPLOAD

                            headers = await detail_page.query_selector_all('h2')
                            for header in headers:
                                header_text = (await header.inner_text()).strip()
                                if "Pozostałe dokumenty postępowania" in header_text:
                                    header_handle = header
                                    next_sibling = await header_handle.evaluate_handle('node => node.parentElement.nextElementSibling')
                                    if next_sibling:
                                        links = await next_sibling.query_selector_all('a')
                                        labels = await next_sibling.query_selector_all('h3')
                                        # pprint.pprint(names)
                                        file_entries = []
                                        for label, link in zip(labels, links):
                                            label_text = await label.inner_text()
                                            href = await link.get_attribute('href')
                                            if not href:
                                                continue
                                            name = (await link.inner_text()).strip()
                                            file_entries.append((label_text, name))

                                        choosen_file = await ai_pick_main_doc(file_entries)
                                        logging.info(f"Choosen: {choosen_file.selected}")
                                        
                                        if choosen_file.selected is not None:
                                            try:
                                                # Get the link corresponding to the chosen file
                                                extraction_service = FileExtractionService()
                                                chosen_link = links[choosen_file.selected["index"]]
                                                # Download the file using the existing method
                                                file_results = await self._download_file_from_link(detail_page, chosen_link, extraction_service)
                                                
                                                # Try to decode and return content from first successful file
                                                for file_content, filename, preview_chars, original_bytes, original_filename in file_results:
                                                    try:
                                                        decoded_content = file_content.decode('utf-8')
                                                        logging.info(f"Content: {decoded_content[:5000]}")
                                                        return decoded_content[:5000]
                                                    except UnicodeDecodeError:
                                                        logging.warning(f"Could not decode {filename} as UTF-8, trying next file if available")
                                                        continue
                                                    except Exception as e:
                                                        logging.error(f"Error processing file {filename}: {e}")
                                                        continue
                                                
                                                logging.warning("No files could be successfully decoded")
                                                return None
                                                
                                            except PlaywrightTimeoutError as e:
                                                logging.error(f"Timeout while downloading file: {e}")
                                                return None
                                            except Exception as e:
                                                logging.error(f"Error during file download process: {e}")
                                                return None
                                        return None

                    else:
                        href = await link.get_attribute("href")
                if href.startswith("/"):
                    href = f"https://ezamowienia.gov.pl{href}"
                ann_page = await context.new_page()
                try:
                    await ann_page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                    await ann_page.wait_for_selector("body", timeout=10000)
                    await detail_page.wait_for_timeout(1000)

                    html = await ann_page.content()

                    # first try new scraper
                    txt = self._scrape_sections_5_1_and_5_1_1(html)
                    if txt:
                        return txt
                finally:
                    await ann_page.close()

                return None
            href = await link.get_attribute("href")
            if not href:
                logging.warning(f"No href: {link}")
                return None
            if href.startswith("/"):
                href = f"https://ezamowienia.gov.pl{href}"

            # ── open the announcement itself ──────────────────
            ann_page = await context.new_page()
            try:
                await ann_page.goto(href, wait_until="domcontentloaded", timeout=30000)
                await ann_page.wait_for_selector("body", timeout=10000)
                await detail_page.wait_for_timeout(1000)

                html = await ann_page.content()
                return self._extract_subject_from_html(html)
            finally:
                await ann_page.close()

        except PlaywrightTimeoutError:
            logging.warning(f"{self.source_type}: timeout while reading subject for {detail_url}")
        except Exception as e:
            logging.error(f"{self.source_type}: cannot get tender subject for {detail_url}: {e}")
        finally:
            await detail_page.close()
        return None

    async def execute(self, inputs: Dict) -> Dict:
        max_pages = inputs.get('max_pages', 50)
        start_date = inputs.get('start_date', None)
        tender_names_index_name = inputs.get('tender_names_index_name', "tenders")
        embedding_model = inputs.get('embedding_model', "text-embedding-3-large")
        if start_date:
            pass
        else:
            pass
        start_dt = None
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                # Navigate to the initial page with retry
                navigated = False
                for attempt in range(MAX_RETRIES):
                    try:
                        await page.goto(self.base_url, timeout=30000) # Increased timeout for initial load
                        await page.wait_for_selector("lib-table table tbody tr", timeout=20000) # Increased timeout
                        navigated = True
                        logging.info(f"{self.source_type}: Initial page loaded successfully.")
                        break # Success
                    except PlaywrightTimeoutError as e:
                        logging.warning(f"{self.source_type}: Initial page load/selector wait failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                        if attempt + 1 == MAX_RETRIES:
                            logging.error(f"{self.source_type}: Error loading initial page {self.base_url} after {MAX_RETRIES} attempts: {e}")
                            await page.close()
                            await browser.close()
                            return {"tenders": [], "metadata": ExtractorMetadata(total_tenders=0, pages_scraped=0)}
                        await asyncio.sleep(random.uniform(2.0, 4.0))

            except Exception as e: # Catch potential non-timeout errors during setup
                 logging.error(f"{self.source_type}: Unexpected error during initial page load setup: {e}")
                 await page.close()
                 await browser.close()
                 return {"tenders": [], "metadata": ExtractorMetadata(total_tenders=0, pages_scraped=0)}
            
            tenders = []
            current_page = 1
            next_button = None
            found_older = False
            while current_page <= max_pages and not found_older:
                logging.info(f"{self.source_type}: Scraping page {current_page}...")
                try:
                    # Wait for table rows with retry for subsequent pages
                    table_loaded = False
                    for attempt in range(MAX_RETRIES):
                         try:
                              await page.wait_for_selector("lib-table table tbody tr", timeout=20000) # Increased timeout
                              table_loaded = True
                              break
                         except PlaywrightTimeoutError as e:
                              logging.warning(f"{self.source_type}: Wait for table on page {current_page} failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                              if attempt + 1 == MAX_RETRIES:
                                   logging.error(f"{self.source_type}: Error waiting for table on page {current_page} after {MAX_RETRIES} attempts. Stopping pagination.")
                                   # Break the outer while loop if table fails consistently
                                   raise e 
                              await asyncio.sleep(random.uniform(2.0, 4.0))
                except Exception as e:
                    # Handle the case where the wait fails after retries
                    break # Stop processing pages if table cannot be loaded

                rows = await page.query_selector_all("lib-table table tbody tr")
                logging.info(f"{self.source_type}: Found {len(rows)} rows on page {current_page}.")
                for row in rows:
                    try:
                        cells = await row.query_selector_all("td")
                        if len(cells) < 10:
                            continue
                        initiation_date_str = await cells[8].inner_text()
                        iso_initiation_date = await self.format_date(initiation_date_str)
                        tender_dt = datetime.strptime(iso_initiation_date, "%Y-%m-%d")
                        details_url = f"https://ezamowienia.gov.pl/mp-client/search/list/{await cells[1].inner_text()}"
                        subject = await self._fetch_tender_subject(context, details_url)
                        if not subject:
                            subject = ""  # graceful fallback: listing title
                        tender_data = {
                            "name": await cells[0].inner_text(),
                            "organization": await cells[4].inner_text(),
                            "location": await cells[5].inner_text(),
                            "submission_deadline": DateStandardizer.standardize_deadline(await cells[7].inner_text()),
                            "initiation_date": iso_initiation_date,
                            "details_url": details_url,
                            "content_type": "tender",
                            "source_type": self.source_type,
                            "tender_subject": subject,    
                        }
                        # Pinecone check for tenders older than start_dt
                        if start_dt and tender_dt < start_dt:
                            # Check if tender exists in Pinecone index
                            try:
                                query_config = QueryConfig(
                                    index_name=tender_names_index_name,
                                    namespace="",
                                    embedding_model=embedding_model
                                )
                                query_tool = QueryTool(config=query_config)
                                filter_conditions = {"details_url": details_url}
                                
                                default_index_results = await query_tool.query_by_id(
                                    id=details_url,
                                    top_k=1,
                                    filter_conditions=filter_conditions
                                )
                                if default_index_results.get("matches"):
                                    logging.info(f"{self.source_type}: Encountered tender dated {iso_initiation_date} older than start_date {start_date} and found in Pinecone. Stopping extraction.")
                                    found_older = True
                                    break
                                else:
                                    # Not in Pinecone, include but set initiation_date to start_dt
                                    tender_data["initiation_date"] = start_date
                                    logging.info(f"{self.source_type}: Encountered tender dated {iso_initiation_date} older than start_date {start_date} but not found in Pinecone. Saving tender...")
                                    try:
                                        tender = Tender(**tender_data)
                                        tenders.append(tender)
                                    except Exception as e:
                                        logging.error(f"{self.source_type}: Error creating tender object: {e}. Skipping tender.")
                                    continue  # Continue to next row
                            except Exception as e:
                                logging.error(f"{self.source_type}: Error querying Pinecone when checking older tender: {e}")
                                found_older = True
                                break

                        try:
                            tender = Tender(**tender_data)
                            tenders.append(tender)
                        except Exception as e:
                            logging.error(f"{self.source_type}: Error creating tender object: {e}. Skipping tender.")
                            continue
                    except Exception as e:
                        logging.error(f"{self.source_type}: Error parsing row on page {current_page}: {e}")
                        continue
                if found_older:
                    break
                
                # Click next page with retry
                next_button = await page.query_selector("lib-paginator nav a.append-arrow:not(.disabled)")
                if next_button:
                    clicked_next = False
                    for attempt in range(MAX_RETRIES):
                        try:
                            logging.info(f"{self.source_type}: Moving to next page...")
                            await next_button.click(timeout=10000) # Add timeout to click
                            await page.wait_for_timeout(2000) # Consider if wait_for_load_state is better
                            clicked_next = True
                            break
                        except PlaywrightTimeoutError as e:
                            logging.warning(f"{self.source_type}: Next page click failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                            if attempt + 1 == MAX_RETRIES:
                                logging.error(f"{self.source_type}: Failed to click next page after {MAX_RETRIES} attempts. Stopping pagination.")
                                break # Stop trying to paginate
                            await asyncio.sleep(random.uniform(2.0, 4.0))
                    
                    if not clicked_next:
                         break # Stop if next click failed after retries
                    current_page += 1
                else:
                    logging.info(f"{self.source_type}: No more pages available.")
                    break # Explicitly break if no next button
            
            # Ensure browser is closed outside the loop
            await browser.close()
            
            metadata = ExtractorMetadata(
                total_tenders=len(tenders),
                pages_scraped=current_page -1 if next_button else current_page # Adjust pages scraped count
            )
            logging.info(f"{self.source_type}: Extraction complete. Extracted {len(tenders)} tenders from {metadata.pages_scraped} pages.")
            return {
                "tenders": tenders,
                "metadata": metadata
            }


    ######################################################
    # find_updates - main entry point for checking updates
    ######################################################
    async def find_updates(
        self,
        tenders_to_monitor: List[TenderAnalysisResult],
        date_str: str
    ) -> Dict[str, List[Tuple[str, bytes, str, str]]]:
        """
        1) Calls mo-board endpoint with `noticeType=NoticeUpdateNotice` for date_str (07:00 to 20:00).
        2) For each returned item, match tenderId with T.A.Result's `tender_url`.
        3) For each matched tender, open detail page, parse:
           - "Pozostałe dokumenty postępowania" => new files from date_str
           - "Ogłoszenia i dokumenty postępowania utworzone w systemie" => if there's a link to an internal "Ogłoszenie..." page, open it, parse full HTML => store as .txt
        4) Compare to existing `uploaded_files` to see what's truly new.
        5) Return dict: { str(tender_id): [ (filename, file_content_bytes), ... ], ... }
        """
        # logging.info(
        #     f"{self.source_type}: Checking for updates on {date_str} for {len(tenders_to_monitor)} tenders."
        # )
        from_dt = f"{date_str}T07:00:00"
        to_dt = f"{date_str}T20:00:00"

        # We'll store final results here:
        #   { "tender_id_as_string": [(filename, file_content), (filename, file_content)], ... }
        updates_found: Dict[str, List[Tuple[str, bytes, str, str]]] = {}

        # 1) Fetch "NoticeUpdateNotice" items with retry
        params = {
            "NoticeType": "NoticeUpdateNotice",
            "PublicationDateFrom": from_dt,
            "PublicationDateTo": to_dt,
            "PageSize": "500"
        }
        updates = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(self.api_url, params=params, timeout=30)
                    resp.raise_for_status()
                    updates = resp.json()
                    break # Success
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logging.warning(f"{self.source_type}: API fetch for updates failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt + 1 == MAX_RETRIES:
                    logging.error(f"{self.source_type}: Error fetching updated notices from {self.api_url} after {MAX_RETRIES} attempts: {e}")
                    return updates_found # Cannot proceed without API data
                await asyncio.sleep(random.uniform(1.0, 3.0)) # Shorter delay for API call
            except Exception as e: # Catch other potential errors like JSON decoding
                 logging.error(f"{self.source_type}: Unexpected error fetching/parsing updates from {self.api_url}: {e}")
                 return updates_found

        if not updates:
            logging.info(f"{self.source_type}: No updated notices found for {date_str} in mo-board.")
            return updates_found

        # Build map for quick checking: we want to see which T.A.Result has which tenderId in `tender_url`
        # Typically your `tender_url` looks like: "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-xxxx"
        # We'll parse out the `ocds-148610-xxxx` part and compare to item["tenderId"] from the JSON
        tender_map = {}
        for tar in tenders_to_monitor:
            # Example: parse "ocds-..." from tar.tender_url
            # If your tender_url is exactly "https://ezamowienia.gov.pl/mp-client/search/list/ocds-148610-c36d5e30-cde6..."
            # We'll just find everything after ".../list/".
            splitted = tar.tender_url.split("/list/")
            if len(splitted) == 2:
                possible_id = splitted[1]
                # often "ocds-148610-c36d5e30-cde6-44a1-a367-65695258493b" 
                tender_map[possible_id] = tar

        logging.info(f"{self.source_type}: Found {len(updates)} items from mo-board. Matching with {len(tender_map)} Tenders...")

        # 2) Filter mo-board items to those that match our T.A.Results
        matched_notices = []
        for item in updates:
            # Example: "tenderId": "ocds-148610-c36d5e30-cde6-44a1-a367-65695258493b"
            mo_board_tid = item.get("tenderId", "")
            if mo_board_tid in tender_map:
                matched_notices.append(item)

        if not matched_notices:
            logging.info(f"{self.source_type}: None of the updated notices matched your Tenders.")
            return updates_found

        extraction_service = FileExtractionService()
        # 3) For each matched notice, open the detail page of that tender
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            for notice_item in matched_notices:
                mo_board_tid = notice_item["tenderId"]
                tar = tender_map[mo_board_tid]

                logging.info(f"{self.source_type}: Found matched updated notice => T.A.Result {tar.id}")
                detail_url = tar.tender_url  # e.g. "https://ezamowienia.gov.pl/mp-client/search/list/ocds-..."

                # We'll parse the detail page for updated docs
                new_docs = await self._detect_updated_docs(
                    context,
                    tar,
                    detail_url,
                    date_str,
                    extraction_service
                )
                if new_docs:
                    # Combine them with any existing new docs
                    tid_str = str(tar.id)
                    if tid_str not in updates_found:
                        updates_found[tid_str] = []
                    updates_found[tid_str].extend(new_docs)

            await browser.close()

        logging.info(f"{self.source_type}: Completed update detection. Found updates for {len(updates_found)} Tenders.")
        return updates_found




    async def _detect_updated_docs(
        self,
        context: BrowserContext,
        tender_result: TenderAnalysisResult,
        details_url: str,
        date_str: str,
        extraction_service: FileExtractionService
    ) -> List[Tuple[str, bytes, str, str]]:
        page = await context.new_page()
        new_docs: List[Tuple[str, bytes, str, str]] = []
        try:
            # Navigate to detail page with retry
            navigated = False
            for attempt in range(MAX_RETRIES):
                try:
                    await page.goto(details_url, wait_until='domcontentloaded', timeout=40000) # Increased timeout
                    navigated = True
                    break # Success
                except PlaywrightTimeoutError as e:
                    logging.warning(f"{self.source_type}: Update detection - Page goto failed ({details_url}, attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    if attempt + 1 == MAX_RETRIES:
                        logging.error(f"{self.source_type}: Failed to navigate to {details_url} for update detection after {MAX_RETRIES} attempts.")
                        await page.close() # Close page before returning
                        return new_docs # Return empty list if navigation fails
                    await asyncio.sleep(random.uniform(2.0, 4.0))
            
            await page.wait_for_timeout(2000)

            # Process "Ogłoszenie" links
            ogloszenia_links = await page.query_selector_all("div.section h3 a[target='_blank']")
            for link in ogloszenia_links:
                 link_text = (await link.inner_text()).strip()
                 if "Ogłoszenie" in link_text:
                    subpage = None
                    try:
                        async with context.expect_page(timeout=20000) as new_page_info: # Timeout for page expectation
                            # Retry clicking the link
                            click_success = False
                            for attempt in range(MAX_RETRIES):
                                try:
                                    await link.click(timeout=10000) # Timeout for the click itself
                                    click_success = True
                                    break
                                except PlaywrightTimeoutError as click_e:
                                    logging.warning(f"{self.source_type}: Ogłoszenie link click failed ('{link_text}', attempt {attempt + 1}/{MAX_RETRIES}): {click_e}")
                                    if attempt + 1 == MAX_RETRIES:
                                        logging.error(f"{self.source_type}: Failed to click Ogłoszenie link '{link_text}' after {MAX_RETRIES} attempts.")
                                        break # Stop trying to click this link
                                    await asyncio.sleep(random.uniform(2.0, 4.0))
                            
                            if not click_success:
                                continue # Skip this link if click failed

                            subpage = await new_page_info.value
                        
                        # Wait for subpage load state with retry
                        subpage_loaded = False
                        for attempt in range(MAX_RETRIES):
                            try:
                                await subpage.wait_for_load_state("domcontentloaded", timeout=30000) # Increased timeout
                                subpage_loaded = True
                                break
                            except PlaywrightTimeoutError as load_e:
                                logging.warning(f"{self.source_type}: Ogłoszenie subpage load failed ('{link_text}', attempt {attempt + 1}/{MAX_RETRIES}): {load_e}")
                                if attempt + 1 == MAX_RETRIES:
                                    logging.error(f"{self.source_type}: Failed to load Ogłoszenie subpage for '{link_text}' after {MAX_RETRIES} attempts.")
                                    break # Stop trying to load this subpage
                                await asyncio.sleep(random.uniform(2.0, 4.0))

                        if not subpage_loaded:
                            if subpage: await subpage.close() # Close if opened but failed to load
                            continue # Skip processing this subpage

                        await subpage.wait_for_timeout(2000)

                        html_body = await subpage.content()
                        text_content = self._html_to_text(html_body)
                        safe_name = link_text.replace(" ", "_").replace("/", "-").replace(":", "")
                        filename = f"{safe_name}.txt"
                        
                        # Generate preview
                        preview_chars = text_content.encode("utf-8")[:200].decode('utf-8', 'ignore')

                        if not any(f.filename == original_filename for f in tender_result.uploaded_files):
                            new_docs.append((filename, text_content.encode("utf-8"), link_text, preview_chars))
                        
                    except PlaywrightTimeoutError as page_expect_e:
                         logging.error(f"{self.source_type}: Timeout expecting Ogłoszenie subpage for '{link_text}': {page_expect_e}")
                         # Subpage might not have been assigned if expect_page timed out
                    except Exception as subpage_e:
                         logging.error(f"{self.source_type}: Error processing Ogłoszenie subpage for '{link_text}': {subpage_e}")
                    finally:
                         if subpage: 
                             await subpage.close()

            # Process "Pozostałe dokumenty postępowania"
            link_items = await page.query_selector_all("app-link-item div.link-item")
            target_date = None
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                logging.warning(f"Bad date_str format: {date_str}")
                await page.close() # Close page before returning
                return new_docs

            for item in link_items:
                item_text = (await item.inner_text()).strip()
                match = re.search(r"Data udostępnienia:\s*([^\)]+)", item_text)
                if not match:
                    continue

                date_portion = match.group(1).strip()
                date_part = date_portion.split(",")[0].strip()  # e.g., "24 lutego 2025"
                
                doc_date = None
                try:
                    doc_date = self._parse_polish_date(date_part)
                except ValueError as date_parse_e:
                    logging.warning(f"{self.source_type}: Could not parse date '{date_part}' in item: {date_parse_e}")
                    continue # Skip item if date is unparseable

                if doc_date != target_date:
                    continue

                links = await item.query_selector_all("a")
                for link in links:
                    link_text = (await link.inner_text()).strip()
                    file_href = await link.get_attribute("href")
                    if not file_href:
                        continue

                    name_label = await item.query_selector("h3.name-label")
                    doc_title = (await name_label.inner_text()).strip() if name_label else "UntitledDoc"
                    
                    # Construct potential filename to check against existing files first
                    # Note: This filename might change if extraction_service produces multiple files or modifies it.
                    # We check the most likely base name.
                    potential_filename_base = f"{doc_title} - {link_text}".replace("/", "_").replace(":", "")
                    if any(f.filename.startswith(potential_filename_base) for f in tender_result.uploaded_files):
                        # logging.info(f"{self.source_type}: Skipping download, file matching '{potential_filename_base}' likely exists.")
                        continue

                    # Call the download helper (which now includes retries)
                    file_results = await self._download_file_from_link(page, link, extraction_service)
                    for file_content, filename, preview_chars, original_bytes, original_filename in file_results:
                         # Double check filename against existing after download/extraction
                         if not any(f.filename == original_filename for f in tender_result.uploaded_files):
                            new_docs.append((file_content, filename, file_href, preview_chars, original_bytes))
                         else:
                            pass

        except Exception as e:
            logging.error(f"{self.source_type}: Error detecting updated docs on {details_url}: {e}")
        finally:
            await page.close()

        return new_docs

    def _parse_polish_date(self, date_string: str) -> date:
        month_map = {
            'stycznia': 1, 'lutego': 2, 'marca': 3,
            'kwietnia': 4, 'maja': 5, 'czerwca': 6,
            'lipca': 7, 'sierpnia': 8, 'września': 9,
            'października': 10, 'listopada': 11, 'grudnia': 12,
        }
        parts = date_string.split()
        if len(parts) < 3:
            raise ValueError(f"Cannot parse date: {date_string}")
        day_str, month_name, year_str = parts[:3]
        day = int(day_str)
        year = int(year_str)
        month = month_map.get(month_name.lower())
        if not month:
            raise ValueError(f"Unknown Polish month: {month_name}")
        return date(year, month, day)

    async def _download_file_from_link(self, page: Page, link, extraction_service: FileExtractionService) -> List[Tuple[bytes, str, str]]:
        """
        Click link => wait for download => read content => return list of (bytes, filename, preview_chars)
        Includes retry logic for the link click.
        """
        temp_dir = None
        results: List[Tuple[bytes, str, str]] = [] # Initialize results list
        unique_id = str(uuid4())
        temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        link_text_for_log = await link.inner_text()

        try:
            download_successful = False
            download = None # Initialize download variable
            async with page.expect_download(timeout=30000) as download_info: # Increased timeout for download event
                # Retry clicking the link
                click_success = False
                for attempt in range(MAX_RETRIES):
                    try:
                        await link.click(timeout=10000) # Timeout for the click itself
                        click_success = True
                        break # Success
                    except PlaywrightTimeoutError as click_e: 
                        logging.warning(f"{self.source_type}: Download link click failed for '{link_text_for_log}' (attempt {attempt + 1}/{MAX_RETRIES}): {click_e}")
                        if attempt + 1 == MAX_RETRIES:
                            logging.error(f"{self.source_type}: Failed to click download link '{link_text_for_log}' after {MAX_RETRIES} attempts.")
                            break # Stop trying to click this link
                        await asyncio.sleep(random.uniform(2.0, 4.0))
                
                if not click_success:
                    # If click failed, cleanup and return empty list
                    if temp_dir and temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    return [] 

                # If click was successful, wait for download info (handled by context manager timeout)
                download = await download_info.value
                download_successful = True # Mark as successful if download object received
            
            # Process download outside the 'with' block if successful
            suggested_name = download.suggested_filename or "document"
            temp_path = temp_dir / suggested_name
            await download.save_as(str(temp_path))
            if temp_path.exists() and temp_path.stat().st_size > 100:
                file_results_from_service = await extraction_service.process_file_async(temp_path)
                # Make sure the tuple structure matches: (content_bytes, filename, preview_chars)
                results.extend(file_results_from_service)
            else:
                logging.warning(f"{self.source_type}: Downloaded file '{suggested_name}' is too small or does not exist at {temp_path}.")
                if temp_path.exists():
                    temp_path.unlink() # Clean up small/empty file

        except PlaywrightTimeoutError as e:
            logging.warning(f"ezamowienia: Playwright timeout in _download_file_from_link for {link_text_for_log if 'link_text_for_log' in locals() else 'unknown link'}: {str(e)}")
            # Fall through to general exception if this is not the one we want to target, or handle specific cleanup
        except Exception as e: # This is the main, outermost exception handler for _download_file_from_link
            error_message = str(e)
            cleaned_error_message = error_message.encode('utf-8', errors='replace').decode('utf-8', 'ignore')
            logging.error(f"ezamowienia: Error processing download for file '{suggested_filename_cleaned if 'suggested_filename_cleaned' in locals() else 'unknown_file'}': {cleaned_error_message}")
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        return results # Return the list of processed file tuples

    def _html_to_text(self, html: str) -> str:
        """
        Simple HTML->text. Production code can use BeautifulSoup, etc.
        """
        import re
        text = re.sub(r"<[^>]+>", "", html)
        text = text.replace("&nbsp;", " ")
        return text.strip()