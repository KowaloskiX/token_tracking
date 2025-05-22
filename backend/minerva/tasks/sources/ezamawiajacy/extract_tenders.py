import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
import random
import shutil
from typing import Any, Dict, Optional, List, Tuple
from urllib.parse import urljoin, urlparse
from uuid import uuid4
from playwright.async_api import Page, Response
from playwright_stealth import stealth_async
from minerva.core.services.vectorstore.file_content_extract.base import ExtractorRegistry
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from playwright.async_api import async_playwright, Page, TimeoutError, Locator, BrowserContext
from bs4 import BeautifulSoup

from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender
from minerva.core.utils.date_standardizer import DateStandardizer
from minerva.tasks.sources.helpers import extract_bzp_plan_fields, scrape_bzp_budget_row

logging.basicConfig(level=logging.INFO)

class EzamawiajacyTenderExtractor:

    def __init__(self, source_type: str = "ezamawiajacy"):
        self.base_list_url = "https://oneplace.marketplanet.pl/web/panel/przetargi/-/notice/list/active?_opUserNoticesPortlet_navigation=active"
        # test
        # self.base_list_url = "https://oneplace.marketplanet.pl/web/panel/przetargi/-/notice/list/active?_opUserNoticesPortlet_navigation=active&_opUserNoticesPortlet_orderByCol=start-date&_opUserNoticesPortlet_orderByType=desc&_opUserNoticesPortlet_resetCur=false&_opUserNoticesPortlet_delta=12&_opUserNoticesPortlet_cur=5"
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

    async def accept_cookies(self, page):
        try:
            cookie_dialog = await page.wait_for_selector("#CybotCookiebotDialog", timeout=4000)
            if cookie_dialog:
                logging.info(f"{self.source_type}: Handling cookie dialog")
                selectors = [
                    "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowall",
                    "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowallSelection"
                ]
                for sel in selectors:
                    try:
                        btn = await page.wait_for_selector(sel, timeout=1500)
                        if btn:
                            await btn.click()
                            await page.wait_for_timeout(500)
                            logging.info(f"{self.source_type}: Cookie dialog dismissed")
                            break
                    except TimeoutError:
                        continue
        except TimeoutError:
            logging.info(f"{self.source_type}: No cookie dialog found")

    async def login(self, page, username: str, password: str):
        """
        Navigates to the login page, accepts cookies, fills in credentials and logs in.
        """
        try:
            login_url = "https://oneplace.marketplanet.pl/poczatek?p_p_id=com_liferay_login_web_portlet_LoginPortlet&p_p_lifecycle=0&p_p_state=maximized&p_p_mode=view&_com_liferay_login_web_portlet_LoginPortlet_mvcRenderCommandName=%2Flogin%2Flogin&saveLastPath=false&"
            await self._goto_with_retry(page, login_url, wait_until='networkidle', timeout=15000, purpose="login")
            await self.accept_cookies(page)
            # Fill in the login form fields.
            await page.fill("input#_com_liferay_login_web_portlet_LoginPortlet_login", username)
            await page.fill("input#_com_liferay_login_web_portlet_LoginPortlet_password", password)
            await page.click("button.btn-primary")  # The login button ("Zaloguj")
            await page.wait_for_load_state("networkidle")
            logging.info(f"{self.source_type}: Successfully logged in as {username}")
        except Exception as e:
            logging.error(f"{self.source_type}: Login failed: {str(e)}")
            raise e

    async def fetch_detail_info(self, context, detail_url: str) -> dict:
        """
        Opens a tender detail page and clicks the "Przechodzę do formularza ofertowego" button.
        Only continues if the redirected URL contains "ezamawiajacy.pl".
        Then extracts relevant detail data:
        - updated_url: the URL after redirection
        - submission_deadline: extracted datetime from the "Data składania wniosków/ofert/opracowań studialnych" field.
        - initiation_date: extracted datetime from the "Publikacja w strefie publicznej" field.
        """
        detail_data = {}
        page = await context.new_page()
        try:
            logging.info(f"{self.source_type}: Navigating to tender detail page: {detail_url}")
            await self._goto_with_retry(page, detail_url, wait_until="networkidle", timeout=15000, purpose="tender detail")
            await page.wait_for_timeout(1000)
            # Look for the button "Przechodzę do formularza ofertowego"
            button = await page.query_selector("button.loading-button")
            updated_url = ''
            if button:
                button_text = await button.inner_text()
                if "Przechodzę do formularza ofertowego" in button_text:
                    async with page.expect_navigation(wait_until="networkidle", timeout=15000):
                        await button.click()
                    new_url = page.url
                    if "ezamawiajacy.pl" not in new_url:
                        logging.info(f"{self.source_type}: Redirected URL does not match desired domain: {new_url}. Skipping tender.")
                        await page.close()
                        return {}
                    else:
                        logging.info(f"{self.source_type}: Redirected to desired details page: {new_url}")
                        updated_url = new_url
                else:
                    logging.info(f"{self.source_type}: Button text did not match desired label. Skipping tender.")
                    await page.close()
                    return {}
            else:
                logging.info(f"{self.source_type}: 'Przechodzę do formularza ofertowego' button not found. Skipping tender.")
                await page.close()
                return {}

            detail_data["updated_url"] = updated_url


            # Proceed to extract further detail data only if the redirected page is correct.
            if "ezamawiajacy.pl" in updated_url:
                # Extract submission_deadline using a regex to capture a datetime in the format YYYY-MM-DD HH:MM
                submission_deadline = await page.evaluate('''() => {
                    const fieldsets = Array.from(document.querySelectorAll('fieldset.mp_common_field'));
                    for (const fs of fieldsets) {
                        const header = fs.querySelector('span.h4span');
                        if (header && header.textContent.includes("Data składania wniosków/ofert/opracowań studialnych:")) {
                            const sec = fs.querySelector("section");
                            if (sec) {
                                const text = sec.textContent;
                                const match = text.match(/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})/m);
                                if (match) return match[1].trim();
                            }
                        }
                    }
                    return "";
                }''')
                if submission_deadline:
                    detail_data["submission_deadline"] = submission_deadline

                # Extract initiation_date using a regex to capture a date in the format YYYY-MM-DD
                initiation_date = await page.evaluate('''() => {
                    const fieldsets = Array.from(document.querySelectorAll('fieldset.mp_common_field'));
                    for (const fs of fieldsets) {
                        const header = fs.querySelector('span.h4span');
                        if (header && header.textContent.includes("Publikacja w strefie publicznej:")) {
                            const sec = fs.querySelector("section");
                            if (sec) {
                                const text = sec.textContent;
                                const match = text.match(/(\d{4}-\d{2}-\d{2})/m);
                                if (match) return match[1].trim();
                            }
                        }
                    }
                    return "";
                }''')
                if initiation_date:
                    detail_data["initiation_date"] = initiation_date

        except Exception as e:
            logging.error(f"{self.source_type}: Error fetching tender detail from {detail_url}: {str(e)}")
        finally:
            await page.close()
        return detail_data

    async def execute(self, inputs: Dict) -> Dict:
        """
        Main entry point for tender extraction.

        inputs dict should include:
          - max_pages: int, maximum number of listing pages to traverse.
          - start_date: str in "YYYY-MM-DD" format to skip tenders older than this date (if tender date is extractable).
          - username: login username/email.
          - password: login password.
        """
        max_pages = 150
        start_date_str = inputs.get("start_date", None)
        username = os.getenv("ONEPLACE_EMAIL")
        password = os.getenv("ONEPLACE_PASSWORD")

        start_dt = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                logging.info(f"{self.source_type}: Starting extraction with start_date: {start_date_str}")
            except ValueError:
                logging.error(f"{self.source_type}: Invalid start_date format: {start_date_str}")
        else:
            logging.info(f"{self.source_type}: Starting extraction with no start_date provided.")

        tenders = []
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                # Log in once before scraping listings.
                login_page = await context.new_page()
                await stealth_async(login_page)
                await self.login(login_page, username, password)
                await login_page.close()

                current_page = 1
                while current_page <= max_pages:
                    list_page = await context.new_page()
                    if current_page == 1:
                        await list_page.wait_for_timeout(1000)
                        await self.accept_cookies(list_page)

                    # await stealth_async(list_page)
                    list_url = f"{self.base_list_url}&_opUserNoticesPortlet_cur={current_page}"
                    try:
                        logging.info(f"{self.source_type}: Navigating to listing page: {list_url}")
                        await self._goto_with_retry(list_page, list_url, wait_until="networkidle", timeout=15000, purpose="listing page")
                        await list_page.wait_for_timeout(1000)
                    except Exception as e:
                        logging.error(f"{self.source_type}: Failed to load listing page {list_url}: {str(e)}")
                        await list_page.close()
                        break

                    # Get all tender rows; rows are contained in <dd> elements with class "list-group-item"
                    tender_rows = await list_page.query_selector_all("dl.list-group > dd.list-group-item")
                    if not tender_rows:
                        logging.info(f"{self.source_type}: No tender rows found on page {current_page}. Stopping.")
                        await list_page.close()
                        break

                    found_recent = False
                    for row in tender_rows:
                        try:
                            title_elem = await row.query_selector("div.notice-name a.notice-url")
                            if not title_elem:
                                continue
                            title = (await title_elem.inner_text()).strip()
                            details_href = await title_elem.get_attribute("href")
                            if details_href and details_href.startswith("/"):
                                detail_url = "https://oneplace.marketplanet.pl" + details_href
                            else:
                                detail_url = details_href

                            # Organization from the row.
                            org_elem = await row.query_selector("div.notice-details span.organization-name")
                            organization = (await org_elem.inner_text()).strip() if org_elem else ""

                            # if start_dt and tender_date and tender_date < start_dt:
                            #     logging.info(f"{self.source_type}: Skipping tender '{title}' published on {tender_date_str} before start_date {start_date_str}")
                            #     continue

                            # Get tender details by following the redirection
                            detail_info = await self.fetch_detail_info(context, detail_url)

                            if not detail_info:
                                logging.info(f"{self.source_type}: Tender '{title}' skipped due to missing or invalid detail page.")
                                continue

                            # Only save tenders where we got detail data from a valid ezamawiajacy.pl page.
                            if detail_info.get("updated_url", None):
                                tender_date_str = detail_info.get("initiation_date", None)
                                if start_dt and tender_date_str and datetime.strptime(tender_date_str, "%Y-%m-%d") < start_dt:
                                    logging.info(f"{self.source_type}: Skipping tender '{title}' published on {tender_date_str} before start_date {start_date_str}")
                                    # continue
                                    metadata = {"total_tenders": len(tenders), "pages_scraped": current_page - 1}
                                    return {"tenders": tenders, "metadata": metadata}

                                tender_data = {
                                    "name": title,
                                    "organization": organization,
                                    "details_url": detail_info.get("updated_url", None),
                                    "source_type": self.source_type,
                                    "location": "",
                                    "submission_deadline": detail_info.get("submission_deadline", ""),
                                    "initiation_date": detail_info.get("initiation_date", ""),
                                }
                                tender_obj = Tender(**tender_data)
                                tenders.append(tender_obj)
                                logging.info(f"{self.source_type}: Extracted tender '{title}'")

                        except Exception as e:
                            logging.error(f"{self.source_type}: Error processing a tender row on page {current_page}: {str(e)}")
                            continue

                    await list_page.close()
                    # if start_dt and not found_recent:
                    #     logging.info(f"{self.source_type}: No more recent tenders found on page {current_page}. Stopping early.")
                    #     break
                    current_page += 1

                metadata = {"total_tenders": len(tenders), "pages_scraped": current_page - 1}
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

    async def goto_with_retries(
        self,
        page: Page,
        url: str,
        max_retries: int = 3,
        wait_until: str = "networkidle",
        timeout: int = 30000
    ) -> Response:
        """
        Navigates to `url` with retries. If a 500 or known internal server error text is found,
        waits a random 2-5s, then retries up to `max_retries` times.
        Returns the final `Response` or raises an exception if it fails after max_retries.
        """
        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"[goto_with_retries] Attempt {attempt}/{max_retries} for {url}")
                response = await page.goto(url, wait_until=wait_until, timeout=timeout)

                if not response:
                    # Sometimes `page.goto()` can return None if the navigation fails outright.
                    logging.warning(f"No response object returned for {url} (attempt {attempt}).")
                    raise ValueError("No response object from page.goto().")

                status = response.status
                logging.info(f"[goto_with_retries] Received status {status} for {url}")

                # 1) Check HTTP status for 500
                if status == 500:
                    if attempt < max_retries:
                        sleep_time = random.uniform(2, 5)
                        logging.warning(
                            f"[goto_with_retries] Got 500 for {url} (attempt {attempt}). "
                            f"Sleeping {sleep_time:.2f}s before retry."
                        )
                        await asyncio.sleep(sleep_time)
                        continue
                    else:
                        logging.error(f"[goto_with_retries] Reached max_retries on {url} with 500 error.")
                        return response

                # 2) Optionally check if the loaded page contains "Wewnętrzny błąd serwera"
                #    (Sometimes servers respond 200 but with an error page content).
                content = await page.content()
                if "Wewnętrzny błąd serwera" in content:
                    if attempt < max_retries:
                        sleep_time = random.uniform(2, 5)
                        logging.warning(
                            f"[goto_with_retries] Found 'Wewnętrzny błąd serwera' text in page content for {url} "
                            f"(attempt {attempt}). Sleeping {sleep_time:.2f}s before retry."
                        )
                        await asyncio.sleep(sleep_time)
                        continue
                    else:
                        logging.error(
                            f"[goto_with_retries] Reached max_retries on {url} with 'Wewnętrzny błąd serwera'."
                        )
                        return response

                # If we get here, no 500 or known error text => success!
                return response

            except Exception as e:
                # Catch any other exceptions (network issues, timeouts, etc.).
                last_exception = e
                if attempt < max_retries:
                    sleep_time = random.uniform(2, 5)
                    logging.warning(
                        f"[goto_with_retries] Exception in attempt {attempt} for {url}: {e}\n"
                        f"Sleeping {sleep_time:.2f}s before retry."
                    )
                    await asyncio.sleep(sleep_time)
                else:
                    # If we've exhausted retries, re-raise or return an error response.
                    logging.error(f"[goto_with_retries] Failed after {max_retries} attempts on {url}. Exception: {e}")
                    raise

        # If we somehow get here without returning, raise the last exception
        if last_exception:
            raise last_exception

        # Fallback if no exception was raised (though we should have returned by now)
        raise RuntimeError(f"goto_with_retries: unhandled state for {url}")
    

    async def handle_login_for_detail_extraction(self, page: Page, details_url: str) -> None:
        try:
            # 1) Accept cookies (if any)
            try:
                cookie_dialog = await page.wait_for_selector("#CybotCookiebotDialog", timeout=4000)
                if cookie_dialog:
                    logging.info("Handling cookie dialog (detail-login)")
                    for sel in [
                        "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowall",
                        "button#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowallSelection"
                    ]:
                        try:
                            btn = await page.wait_for_selector(sel, timeout=1500)
                            if btn:
                                await btn.click()
                                await page.wait_for_timeout(500)
                                logging.info("Cookie dialog dismissed (detail-login)")
                                break
                        except TimeoutError:
                            continue
            except TimeoutError:
                logging.info("No cookie dialog found (detail-login)")

            """
            Navigates to the login page, accepts cookies, fills in credentials and logs in.
            """
            try:
                
                email = os.getenv("ONEPLACE_EMAIL")
                password = os.getenv("ONEPLACE_PASSWORD")
                await self.accept_cookies(page)
                # Fill in the login form fields.
                await page.fill("input#_com_liferay_login_web_portlet_LoginPortlet_login", email)
                await page.fill("input#_com_liferay_login_web_portlet_LoginPortlet_password", password)
                await page.click("button.btn-primary")  # The login button ("Zaloguj")
                await page.wait_for_load_state("networkidle")
                logging.info(f"{self.source_type}: Successfully logged in as {email}")
            except Exception as e:
                logging.error(f"{self.source_type}: Login failed: {str(e)}")
                raise e

            # 3) Now navigate back to the details URL
            #    (ensures we end up where we intended, not on the listing)
            await page.wait_for_timeout(3000)
            logging.info(f"(detail-login) Navigating back to: {details_url}")
            await page.goto(details_url, wait_until='networkidle', timeout=30000)

        except Exception as ex:
            logging.error(f"Error in handle_login_for_detail_extraction: {ex}")
            raise


    async def extract_files_from_detail_page(
        self,
        context,
        details_url: str,
    ) -> list:
        """
        Robust version. Handles case where attachment table is present but has zero rows.
        Also extracts the Ogłoszenie page as a virtual file if present.
        """
        processed_files: list = []
        extraction_service = FileExtractionService()

        tmp_dir = Path.cwd() / "temp_downloads" / str(uuid4())
        tmp_dir.mkdir(parents=True, exist_ok=True)

        page = await context.new_page()
        DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT_MS", "60000"))

        try:
            await self.goto_with_retries(page, details_url, max_retries=3)

            # Optional login
            try:
                await page.wait_for_selector("div#innerContent.subpage", timeout=5_000)
                login_link = page.locator(
                    "a.btn1line.mp_common_field_btn.w120px.ac"
                    "[href^='https://oneplace.marketplanet.pl/web/panel/redirect']"
                )
                if await login_link.count():
                    async with page.expect_navigation():
                        await login_link.first.click()
                    await self.handle_login_for_detail_extraction(page, details_url)
            except Exception:
                pass

            # Wait for file *table* to appear (not rows)
            try:
                await page.wait_for_selector("table.mp_gridTable", timeout=20_000)
            except TimeoutError:
                logging.warning("No file table present at %s", details_url)
                return processed_files

            # --- Ogłoszenie extraction ---
            ogloszenie_row = await page.query_selector('tr.fileDataRow#_-2')
            if ogloszenie_row:
                # Get the text content of the "name" cell
                name_cell = await ogloszenie_row.query_selector('td.text.long')
                name_text = (await name_cell.inner_text()).strip() if name_cell else ""
                label = name_text.lower()
                if "ogłoszenie" not in label and "ogloszenie" not in label:
                    logging.info(f"Skipping row id _-2 because its label is not Ogłoszenie: '{name_text}'")
                else:
                    ogloszenie_url = await page.evaluate(
                        """(tr) => window.jQuery ? jQuery(tr).data('downloadPostUrl') : null""",
                        ogloszenie_row
                    )
                    if ogloszenie_url:
                        origin = urlparse(page.url)._replace(path="", params="", query="", fragment="").geturl()
                        ogloszenie_abs_url = urljoin(origin, ogloszenie_url)
                        logging.info(f"Found Ogłoszenie preview URL: {ogloszenie_abs_url}")

                        ogloszenie_page = await context.new_page()
                        try:
                            await self.goto_with_retries(ogloszenie_page, ogloszenie_abs_url, max_retries=3)
                            try:
                                await ogloszenie_page.wait_for_selector('iframe[name="bzpNoticeContent"]', timeout=10_000)
                                iframe = await ogloszenie_page.query_selector('iframe[name="bzpNoticeContent"]')
                                if iframe is None:
                                    logging.info(f"No Ogłoszenie iframe found at {ogloszenie_abs_url}")
                                else:
                                    iframe_src = await iframe.get_attribute("src")
                                    if iframe_src:
                                        iframe_abs_url = urljoin(ogloszenie_abs_url, iframe_src)
                                        iframe_page = await context.new_page()
                                        try:
                                            await self.goto_with_retries(iframe_page, iframe_abs_url, max_retries=3)
                                            html = await iframe_page.content()
                                            soup = BeautifulSoup(html, "html.parser")
                                            text = soup.get_text(separator="\n", strip=True)
                                            preview = text[:200]
                                            ogloszenie_content_bytes = text.encode("utf-8")
                                            processed_files.append((
                                                ogloszenie_content_bytes,
                                                "Ogloszenie.txt",
                                                details_url,
                                                preview,
                                                ogloszenie_content_bytes
                                            ))
                                            logging.info("Extracted Ogłoszenie content as Ogloszenie.txt")
                                        finally:
                                            await iframe_page.close()
                                    else:
                                        logging.info(f"Ogłoszenie iframe at {ogloszenie_abs_url} has no src attribute")
                            except TimeoutError:
                                logging.info(f"No Ogłoszenie iframe found at {ogloszenie_abs_url}")
                            except Exception as ex:
                                logging.warning(f"Error extracting Ogłoszenie iframe at {ogloszenie_abs_url}: {ex}")
                        finally:
                            await ogloszenie_page.close()

            # --- Normal file extraction ---
            file_rows = await page.query_selector_all("table.mp_gridTable tr.fileDataRow")
            if not file_rows:
                logging.info("No attachments found on %s (table present but zero files)", details_url)
                return processed_files

            file_data = await page.evaluate(
                """() => [...document.querySelectorAll("tr.fileDataRow")]
                    .filter(tr => tr.id !== "_-2")
                    .map(tr => ({
                        name: tr.querySelector("td.text.long")?.innerText.trim() || "Unnamed",
                        url : (window.jQuery ? jQuery(tr).data('downloadPostUrl') : null) || ''
                    }))
                    .filter(f => f.url);"""
            )

            if not file_data:
                logging.warning("No attachments to download at %s (rows found but no usable attachments)", details_url)
                # Still return processed_files (may contain Ogloszenie.txt)
                return processed_files

            origin = urlparse(page.url)._replace(path="", params="", query="", fragment="").geturl()

            for f in file_data:
                file_name = f["name"]
                abs_url = urljoin(origin, f["url"])
                # if file_name.lower().endswith('.zip'):
                #     logging.info(f"Skipping .zip file: {file_name}")
                #     continue

                logging.info("Downloading %s …", file_name)

                try:
                    async with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as dl_info:
                        await page.evaluate(
                            """url => {
                                const form = Object.assign(document.createElement('form'), {
                                    method: 'POST',
                                    action: url,
                                    style : 'display:none'
                                });
                                document.body.appendChild(form);
                                form.submit();
                                setTimeout(() => form.remove(), 1000);
                            }""",
                            abs_url,
                        )

                    download = await dl_info.value
                    tmp_path = tmp_dir / file_name
                    await download.save_as(str(tmp_path))

                    # Use async wrapper
                    processed_results = await extraction_service.process_file_async(tmp_path)
                    for file_content, filename, preview_chars, original_bytes, original_filename in processed_results:
                        processed_files.append((file_content, filename, details_url, preview_chars, original_bytes))

                except Exception as e:
                    logging.error(f"Failed to download/process file {file_name} from {abs_url}: {e}")
                    continue  # skip this file, keep going


            logging.info("Processed %d attachment(s) from %s",
                        len(processed_files), details_url)

            # === Start BZP Budget Extraction Logic ===
            plan_num, plan_id = None, None
            pdf_extractor = ExtractorRegistry().get('.pdf')
            for file_content, filename, url, preview_chars, original_bytes in processed_files:
                try:
                    if filename.lower().endswith(".pdf"):
                        temp_pdf_path = tmp_dir / filename 
                        if temp_pdf_path.exists() and pdf_extractor:
                            text = pdf_extractor.extract_text_as_string(temp_pdf_path)
                            bzp_num, bzp_id = extract_bzp_plan_fields(text)
                            if bzp_num and bzp_id:
                                plan_num, plan_id = bzp_num, bzp_id
                                logging.info(f"{self.source_type}: Found BZP details in {filename}: Plan={plan_num}, ID={plan_id}")
                                break
                    elif filename == "Ogloszenie.txt":
                        text = file_content.decode("utf-8", errors="ignore")
                        bzp_num, bzp_id = extract_bzp_plan_fields(text)
                        if bzp_num and bzp_id:
                            plan_num, plan_id = bzp_num, bzp_id
                            logging.info(f"{self.source_type}: Found BZP details in Ogloszenie.txt: Plan={plan_num}, ID={plan_id}")
                            break
                except Exception as e:
                    logging.warning(f"{self.source_type}: Error extracting/searching {filename} for BZP fields: {e}")

            if plan_num and plan_id:
                plan_short_id = plan_id.split()[0] if plan_id else plan_id
                logging.info(f"{self.source_type}: Attempting to scrape BZP budget for Plan={plan_num}, PosID={plan_short_id}")
                try:
                    budget_row_data = await scrape_bzp_budget_row(context, plan_num, plan_short_id)
                    if budget_row_data:
                        row_str, bzp_url = budget_row_data
                        budget_info = (
                            f"---\n"
                            f"**Dane z planu postępowań BZP**\n"
                            f"Przewidywany budżet/Orientacyjna wartość/cena zamówienia:\n{row_str}\n"
                        )
                        logging.info(f"{self.source_type}: Successfully scraped BZP budget row.")
                    else:
                        import urllib.parse
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
            # === End BZP Budget Extraction Logic ===

            return processed_files

        finally:
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass
            await page.close()

    async def _extract_new_files_from_detail_page(
        self,
        details_url: str,
        last_check_date: datetime
    ) -> List[Tuple[str, bytes, str, str]]:
        """
        Robust version: Handles case where attachment table is present but has zero file rows.
        """
        new_files: List[Tuple[str, bytes, str, str]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, slow_mo=200)
            new_context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            )
            page = await new_context.new_page()
            temp_dir_path = Path(os.getcwd()) / "temp_downloads" / str(uuid4())
            temp_dir_path.mkdir(parents=True, exist_ok=True)

            extraction_service = FileExtractionService()

            try:
                # Robust retries for navigation
                logging.info(f"[find_updates] Navigating to detail page: {details_url}")
                response = await self.goto_with_retries(
                    page=page,
                    url=details_url,
                    max_retries=3,
                    wait_until="networkidle",
                    timeout=30000
                )
                if response.status == 500:
                    logging.warning(f"[find_updates] Could not load detail page (HTTP 500): {details_url}")
                    return new_files

                # Optional forced login
                try:
                    await page.wait_for_selector("div#innerContent.subpage", timeout=5000)
                    logging.info("Login subpage detected on detail view; attempting detail-based login.")
                    login_link = page.locator(
                        "a.btn1line.mp_common_field_btn.w120px.ac[href^='https://oneplace.marketplanet.pl/web/panel/redirect']"
                    )
                    if await login_link.count() > 0:
                        logging.info("Clicking 'Zaloguj' link to trigger login redirect.")
                        async with page.expect_navigation(timeout=10000):
                            await login_link.first.click()
                        await self.handle_login_for_detail_extraction(page, details_url)
                except TimeoutError:
                    logging.info("No forced login subpage or timed out checking for it. Proceeding.")

                # Wait for attachment table, not rows!
                try:
                    await page.wait_for_selector("table.mp_gridTable", state="attached", timeout=20000)
                except TimeoutError:
                    logging.warning("[find_updates] No attachment table found at %s", details_url)
                    return new_files

                # Now look up rows. If none, skip
                file_rows = await page.query_selector_all("table.mp_gridTable tr.fileDataRow")
                if not file_rows:
                    logging.info("[find_updates] No attachments found on %s (table present but no file rows)", details_url)
                    return new_files

                file_data = await page.evaluate('''
                    () => {
                        const rows = document.querySelectorAll('tr.fileDataRow');
                        const extracted = [];
                        rows.forEach(tr => {
                            if (!tr.id || tr.id === '_-2') return;
                            const nameCell = tr.querySelector('td.text.long');
                            const dateCell = tr.querySelector('td.date-time');
                            const scriptData = window.jQuery ? jQuery(tr).data() : {};
                            if (nameCell && dateCell && scriptData && scriptData.downloadPostUrl) {
                                extracted.push({
                                    name: nameCell.innerText.trim(),
                                    uploadDate: dateCell.innerText.trim(),
                                    downloadUrl: scriptData.downloadPostUrl
                                });
                            }
                        });
                        return extracted;
                    }
                ''')

                if not file_data:
                    logging.info("[find_updates] No file rows extracted from table.")
                    return new_files

                for item in file_data:
                    file_name = item["name"]
                    raw_date = item["uploadDate"]
                    download_url = item["downloadUrl"]

                    # Parse date robustly
                    try:
                        if ":" in raw_date:
                            file_date = datetime.strptime(raw_date, "%Y-%m-%d %H:%M")
                        else:
                            file_date = datetime.strptime(raw_date, "%Y-%m-%d")
                    except Exception:
                        logging.warning(f"[find_updates] Failed to parse date '{raw_date}' for file {file_name}.")
                        continue

                    if file_date <= last_check_date:
                        logging.warning(f"[find_updates] Skipping older file: '{file_date}' for file {file_name}.")
                        continue

                    try:
                        logging.info(f"[find_updates] Downloading NEW file '{file_name}' dated {raw_date} from {details_url}")
                        async with page.expect_download(timeout=30000) as download_info:
                            js_code = f'''
                                (() => {{
                                    const form = document.createElement('form');
                                    form.method = 'POST';
                                    form.action = '{download_url}';
                                    document.body.appendChild(form);
                                    form.submit();
                                    document.body.removeChild(form);
                                }})()
                            '''
                            await page.evaluate(js_code)
                            download = await download_info.value
                            temp_path = temp_dir_path / file_name
                            await download.save_as(str(temp_path))

                            # Use async wrapper
                            processed_results = await extraction_service.process_file_async(temp_path)
                            for file_content, filename, preview_chars, original_bytes, original_filename in processed_results:
                                new_files.append((file_content, filename, details_url, preview_chars, original_bytes))

                            if temp_path.exists():
                                temp_path.unlink()

                    except Exception as download_err:
                        logging.error(f"[find_updates] Error downloading file '{file_name}' => {download_err}")

            except Exception as main_err:
                logging.error(f"[find_updates] Error extracting files from {details_url}: {main_err}")
            finally:
                if temp_dir_path.exists():
                    shutil.rmtree(temp_dir_path, ignore_errors=True)
                await page.close()
                await new_context.close()

        return new_files

    async def find_updates(
        self,
        tenders_to_monitor: List["TenderAnalysisResult"]  # type: ignore
    ) -> Dict[str, List[Tuple[str, bytes, str, str]]]:
        """
        For each tender in tenders_to_monitor:
          - Determine its "last_check_date" (updated_at if exists, else created_at)
          - Scrape all attachments from the detail page
          - Parse their upload date
          - If upload_date > last_check_date, download them
        Returns a dict: { "tender_id_str": [(filename, file_bytes, file_url, preview_chars), ...], ... }
        """
        updates_found: Dict[str, List[Tuple[str, bytes, str, str]]] = {}

        for tender in tenders_to_monitor:
            # Determine the date to compare
            if tender.updated_at:
                last_check_date = tender.updated_at
            else:
                last_check_date = tender.created_at  # fallback

            if not tender.tender_url:
                logging.warning(f"[find_updates] Tender {tender.id} missing 'tender_url'; skipping.")
                continue

            # Scrape new files
            newer_files = await self._extract_new_files_from_detail_page(
                details_url=tender.tender_url,
                last_check_date=last_check_date
            )

            # If we found any new attachments, store them
            if newer_files:
                updates_found[str(tender.id)] = newer_files

        return updates_found