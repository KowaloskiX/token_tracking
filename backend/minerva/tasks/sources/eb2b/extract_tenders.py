import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from uuid import uuid4

from minerva.core.models.extensions.tenders.tender_analysis import TenderAnalysisResult
from playwright.async_api import async_playwright, Page
from minerva.core.utils.date_standardizer import DateStandardizer
from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender
from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool


class Eb2bTenderExtractor:
    """
    Extractor for tenders from platforma.eb2b.com.pl with improved pagination handling.
    Uses stable selectors instead of ExtJS's dynamic IDs.
    
    This version ensures that pages and the browser are closed in all edge cases.
    Only key events are logged: retrying to load, timeouts, and scraped URLs (with extractor source name).
    """

    def __init__(self, base_url: str = "https://platforma.eb2b.com.pl"):
        self.base_url = base_url.rstrip("/")
        self.list_url = f"{self.base_url}/open-auctions.html"
        self.source_type = "eb2b"

    async def _goto_with_retry(
        self,
        page: Page,
        url: str,
        wait_until: str = "networkidle",
        timeout: int = 60000,
        retries: int = 2
    ):
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

    async def execute(self, inputs: Dict) -> Dict:
        max_pages = inputs.get("max_pages", 50)
        start_date_str = inputs.get("start_date")
        tender_names_index_name = inputs.get('tender_names_index_name', "tenders")
        embedding_model = inputs.get('embedding_model', "text-embedding-3-large")
        start_dt = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
            except Exception as e:
                logging.error(f"Could not parse start_date for {self.source_type}: {start_date_str}: {e}")

        tenders: List[Tender] = []
        current_page = 0
        found_older = False
        browser = None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                await self._goto_with_retry(page, self.list_url, timeout=60000)
                await page.wait_for_load_state("networkidle")
                await self._accept_cookies_if_present(page)
                await page.wait_for_selector("table.x-grid-table", state="visible", timeout=30000)

                while current_page < max_pages and not found_older:
                    if current_page > 0:
                        success = False
                        for attempt in range(3):
                            try:
                                success = await self._navigate_to_next_page(page)
                                if success:
                                    break
                                await page.wait_for_timeout(5000)
                            except Exception as e:
                                logging.error(f"Navigation error on attempt {attempt + 1} for {self.source_type}: {e}")
                                await page.wait_for_timeout(5000)
                        if not success:
                            logging.error(f"Failed to navigate to next page for {self.source_type} after 3 attempts")
                            break

                    await page.wait_for_timeout(2000)
                    rows = await page.query_selector_all("tr.x-grid-row")
                    if not rows:
                        await page.wait_for_timeout(3000)
                        rows = await page.query_selector_all("tr.x-grid-row")
                        if not rows:
                            logging.error(f"No rows found on page {current_page + 1} for {self.source_type} after retry")
                            break

                    for row in rows:
                        try:
                            columns = await row.query_selector_all("td.x-grid-cell")
                            if len(columns) < 17:
                                continue
                            detail_link_el = await columns[1].query_selector("a")
                            if not detail_link_el:
                                continue
                            detail_href = await detail_link_el.get_attribute("href")
                            detail_url = self._format_detail_url(detail_href)
                            initiation_raw = (await columns[15].inner_text()).strip()
                            initiation_date_formatted = ""
                            dt_obj = None
                            if initiation_raw:
                                try:
                                    dt_str = initiation_raw.split(" ")[0]
                                    dt_obj = datetime.strptime(dt_str, "%Y-%m-%d")
                                    initiation_date_formatted = dt_obj.strftime("%Y-%m-%d")
                                except Exception as e:
                                    logging.warning(f"Unable to parse initiation_date for row for {self.source_type}: {initiation_raw} => {e}")
                            # Pinecone check for tenders older than start_dt
                            if start_dt and dt_obj and dt_obj < start_dt:
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
                                        logging.info(f"{self.source_type}: Encountered tender dated {initiation_date_formatted} older than start_date {start_date_str} and found in Pinecone. Stopping extraction.")
                                        found_older = True
                                        break
                                    else:
                                        # Not in Pinecone, include but set initiation_date to start_dt
                                        columns = await row.query_selector_all("td.x-grid-cell")
                                        name_el = await columns[4].query_selector("a")
                                        name_text = (
                                            (await name_el.inner_text()).strip()
                                            if name_el
                                            else (await columns[4].inner_text()).strip()
                                        )
                                        organization = (await columns[6].inner_text()).strip()
                                        submission_raw = (await columns[16].inner_text()).strip()
                                        submission_deadline = DateStandardizer.standardize_deadline(submission_raw)
                                        tender_data = {
                                            "name": name_text,
                                            "organization": organization,
                                            "location": "",
                                            "submission_deadline": submission_deadline,
                                            "initiation_date": start_dt.strftime("%Y-%m-%d"),
                                            "details_url": detail_url,
                                            "content_type": "tender",
                                            "source_type": self.source_type,
                                        }
                                        try:
                                            t_obj = Tender(**tender_data)
                                            tenders.append(t_obj)
                                            logging.info(f"{self.source_type}: Encountered tender dated {initiation_date_formatted} older than start_date {start_date_str} but not found in Pinecone. Saving tender...")
                                        except Exception as te:
                                            logging.error(f"Error creating Tender object for {self.source_type} at URL: {detail_url}")
                                        continue  # Continue to next row
                                except Exception as e:
                                    logging.error(f"{self.source_type}: Error querying Pinecone when checking older tender: {e}")
                                    found_older = True
                                    break
                            # ...existing code for normal case...
                            tender_obj = await self._parse_tender_row(row, start_dt)
                            if tender_obj is None:
                                found_older = True
                                break
                            tenders.append(tender_obj)
                            logging.info(f"Scraped URL for {self.source_type}: {tender_obj.details_url}")
                        except Exception as e:
                            logging.error(f"Error processing row for {self.source_type}: {e}")
                            continue

                    if found_older:
                        break

                    current_page += 1

                for tender in tenders:
                    try:
                        detail_data = await self.extract_extra_info_from_details(context, tender.details_url)
                        if "Województwo" in detail_data:
                            tender.location = detail_data["Województwo"]
                        if "Organizator" in detail_data:
                            tender.organization = detail_data["Organizator"]
                    except Exception as e:
                        logging.error(f"Error extracting details for tender {tender.details_url} for {self.source_type}: {e}")

        except Exception as e:
            logging.error(f"Critical error during scraping for {self.source_type}: {e}")
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    logging.error(f"Error closing browser for {self.source_type}: {e}")

        metadata = ExtractorMetadata(total_tenders=len(tenders), pages_scraped=current_page)
        return {"tenders": tenders, "metadata": metadata}

    async def _navigate_to_next_page(self, page: Page) -> bool:
        try:
            current_data = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('tr.x-grid-row');
                    return Array.from(rows).map(row => {
                        const cells = row.querySelectorAll('td.x-grid-cell');
                        const id = cells[1]?.textContent?.trim() || '';
                        const name = cells[4]?.textContent?.trim() || '';
                        return `${id}-${name}`;
                    });
                }
            """)
            if not current_data:
                logging.error(f"No rows found before navigation for {self.source_type}")
                return False

            # Navigate using ExtJS store
            navigation_success = await page.evaluate("""
                () => new Promise((resolve) => {
                    try {
                        const grid = Ext.ComponentQuery.query('grid')[0];
                        if (!grid) {
                            resolve(false);
                            return;
                        }
                        const store = grid.getStore();
                        if (!store) {
                            resolve(false);
                            return;
                        }
                        const loadListener = {
                            load: function(store, records, successful) {
                                store.un('load', loadListener.load);
                                if (successful) {
                                    grid.getView().refresh();
                                }
                                resolve(successful);
                            },
                            single: true
                        };
                        store.on('load', loadListener.load);
                        const currentPage = store.currentPage || 1;
                        store.loadPage(currentPage + 1);
                        setTimeout(() => {
                            store.un('load', loadListener.load);
                            resolve(false);
                        }, 15000);
                    } catch (e) {
                        resolve(false);
                    }
                })
            """)
            if not navigation_success:
                logging.error(f"Store navigation failed for {self.source_type}")
                return False

            await page.wait_for_timeout(3000)
            new_data = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('tr.x-grid-row');
                    return Array.from(rows).map(row => {
                        const cells = row.querySelectorAll('td.x-grid-cell');
                        const id = cells[1]?.textContent?.trim() || '';
                        const name = cells[4]?.textContent?.trim() || '';
                        return `${id}-${name}`;
                    });
                }
            """)
            if not new_data:
                logging.error(f"No rows found after navigation for {self.source_type}")
                return False

            any_different = any(item not in current_data for item in new_data)
            if not any_different:
                logging.error(f"Page data did not change after navigation for {self.source_type}")
                return False

            return True
        except Exception as e:
            logging.error(f"Error during pagination for {self.source_type}: {e}")
            return False

    async def _parse_tender_row(self, row, start_dt: Optional[datetime]) -> Optional[Tender]:
        columns = await row.query_selector_all("td.x-grid-cell")
        if len(columns) < 17:
            return None

        detail_link_el = await columns[1].query_selector("a")
        if not detail_link_el:
            return None

        detail_href = await detail_link_el.get_attribute("href")
        detail_url = self._format_detail_url(detail_href)
        tender_id = (await detail_link_el.inner_text()).strip()

        name_el = await columns[4].query_selector("a")
        name_text = (
            (await name_el.inner_text()).strip()
            if name_el
            else (await columns[4].inner_text()).strip()
        )
        organization = (await columns[6].inner_text()).strip()
        initiation_raw = (await columns[15].inner_text()).strip()
        submission_raw = (await columns[16].inner_text()).strip()
        submission_deadline = DateStandardizer.standardize_deadline(submission_raw)

        initiation_date_formatted = ""
        if initiation_raw:
            try:
                dt_str = initiation_raw.split(" ")[0]
                dt_obj = datetime.strptime(dt_str, "%Y-%m-%d")
                initiation_date_formatted = dt_obj.strftime("%Y-%m-%d")
                if start_dt and dt_obj < start_dt:
                    return None
            except Exception as e:
                logging.warning(f"Unable to parse initiation_date for {tender_id} for {self.source_type}: {initiation_raw} => {e}")

        return Tender(
            name=name_text,
            organization=organization,
            location="",
            submission_deadline=submission_deadline,
            initiation_date=initiation_date_formatted,
            details_url=detail_url,
            content_type="tender",
            source_type=self.source_type,
        )

    def _format_detail_url(self, partial_href: str) -> str:
        if partial_href.startswith("http"):
            return partial_href
        return f"{self.base_url}{partial_href}"

    async def _accept_cookies_if_present(self, page: Page):
        try:
            button = await page.query_selector(".modal-cacsp-btn-accept")
            if button:
                await button.click()
                await page.wait_for_timeout(1000)
                return

            cookie_popup = await page.query_selector("#window-1010-body")
            if cookie_popup:
                accept_button = await page.query_selector("button:has-text('Akceptuję')")
                if not accept_button:
                    accept_button = await page.query_selector("a:has-text('Akceptuję')")
                if accept_button:
                    await accept_button.click()
                    await page.wait_for_timeout(1000)
        except Exception:
            pass

    async def extract_extra_info_from_details(self, context, details_url: str) -> Dict[str, str]:
        info = {}
        page = await context.new_page()
        try:
            await self._goto_with_retry(page, details_url, timeout=60000)
            await page.wait_for_load_state("networkidle")
            table = await page.wait_for_selector(
                "table.app-simple-preview-table",
                state="visible",
                timeout=8000
            )
            if table:
                rows = await table.query_selector_all("tr")
                for row in rows:
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 2:
                        label = (await cells[0].inner_text()).strip().rstrip(":")
                        value = (await cells[1].inner_text()).strip()
                        value = " ".join(value.split())
                        info[label] = value
        except Exception as e:
            logging.error(f"Detail extraction error for {details_url} for {self.source_type}: {e}")
        finally:
            await page.close()
        return info
    
    async def _handle_cookie_dialog(self, page: Page) -> None:  # noqa: N802
        """Dismiss the cookie banner (Bootstrap or legacy ExtJS)."""

        try:
            # --- New Bootstrap modal ---------------------------------------------------
            if await page.query_selector("h4#cookie-modalLabel"):
                btn = await page.query_selector("button#acceptCookies")
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(500)
                    return

            # --- Legacy ExtJS windows --------------------------------------------------
            button = await page.query_selector(".modal-cacsp-btn-accept")
            if button:
                await button.click()
                await page.wait_for_timeout(500)
                return

            popup = await page.query_selector("#window-1010-body")
            if popup:
                accept = await page.query_selector("button:has-text('Akceptuję')") or (
                    await page.query_selector("a:has-text('Akceptuję')")
                )
                if accept:
                    await accept.click()
                    await page.wait_for_timeout(500)
        except Exception as exc:  # pragma: no cover
            logging.error("%s – cookie dialog handling failed: %s", self.source_type, exc)


    # ---------------------------------------------------------------------------
    # 2. Download files – one‑by‑one --------------------------------------------
    # ---------------------------------------------------------------------------

    async def _click_row_checkbox(self, page: Page, idx: int) -> bool:  # noqa: N802
        """Tick (or untick) the checkbox of *idx*‑th attachment row (0‑based).

        Uses a three‑level fallback to cope with Ext JS quirks.
        """

        try:
            # --- 1. ExtJS API ---------------------------------------------------------
            ok = await page.evaluate(
                """
                (rowIdx) => {
                    try {
                        const tp = Ext.ComponentQuery.query('tabpanel')[0];
                        const tab = tp ? tp.getActiveTab() : null;
                        const grid = tab ? tab.down('grid') : null;
                        if (!grid) return false;
                        const view = grid.getView();
                        const rec  = view.getStore().getAt(rowIdx);
                        if (!rec) return false;
                        const sm = grid.getSelectionModel();
                        if (sm.isSelected(rec)) {
                            sm.deselect(rec);
                        } else {
                            sm.select(rec, true, true);
                        }
                        return true;
                    } catch (_) {
                        return false;
                    }
                }
                """,
                idx,
            )
            if ok:
                return True

            # --- 2. Click the whole checker cell ------------------------------------
            row = page.locator("tr.x-grid-row").nth(idx)
            await row.scroll_into_view_if_needed()
            cell = row.locator("td.x-grid-cell-row-checker")
            if await cell.count():
                await cell.click(force=True, timeout=2000)
                return True

            # --- 3. Click the inner div ----------------------------------------------
            checker = row.locator("div.x-grid-row-checker")
            await checker.click(force=True, timeout=2000)
            return True

        except Exception as exc:
            logging.debug("Row %s checkbox click failed: %s", idx, exc)
            return False
        
    async def _popup_denies_access(self, page: Page) -> bool:
        """Return *True* if the *apply for participation* message‑box is open."""

        box = await page.query_selector("div.x-message-box")
        if not box:
            return False
        txt = (await box.inner_text()).lower()
        return any(needle in txt for needle in {
            "aby mieć dostęp do załączników": "PL",  # Polish original
            "to gain access to attachments": "EN",  # English platform locale
        })


    async def _dismiss_popup(self, page: Page) -> None:
        """Click **OK** on the access‑denied popup (best‑effort)."""

        try:
            ok_btn = await page.query_selector("div.x-message-box button:has-text('OK')")
            if ok_btn:
                await ok_btn.click()
        except Exception:  # pragma: no cover
            pass

    async def extract_files_from_detail_page(
        self,
        context,
        details_url: str,
    ) -> List[Tuple[bytes, str, Optional[str]]]:  # noqa: N802
        """Iterate over every organiser attachment and download it individually.

        A *seen* set ensures the same file isn’t grabbed twice, fixing the
        duplicated‑last‑attachment bug reported by users in May 2025.
        """

        processed: List[Tuple[bytes, str, Optional[str]]] = []
        seen: Set[str] = set()
        extraction_service = FileExtractionService()
        tmp_root = Path(os.getcwd()) / "temp_downloads" / str(uuid4())
        tmp_root.mkdir(parents=True, exist_ok=True)

        page = await context.new_page()
        try:
            await self._goto_with_retry(page, details_url, timeout=60_000)
            await page.wait_for_load_state("networkidle")
            await self._handle_cookie_dialog(page)

            # --- Switch to attachment tab --------------------------------------------
            ok = await page.evaluate(
                """
                () => {
                    const tp = Ext.ComponentQuery.query('tabpanel')[0];
                    if (!tp) return false;
                    const tab = tp.items.items.find(t => t.title === 'Załączniki organizatora' || t.title === "Sponsor's attachments");
                    if (!tab) return false;
                    tp.setActiveTab(tab);
                    return true;
                }
                """,
            )
            if not ok:
                logging.error("%s – cannot open attachments tab: %s", self.source_type, details_url)
                return []
            await page.wait_for_timeout(1200)

            # await page.wait_for_selector("tr.x-grid-row", timeout=3_000)

            rows = await page.query_selector_all("tr.x-grid-row")
            for idx, _ in enumerate(rows):
                # Skip if we’ve already processed a file with this filename
                try:
                    fname = await page.evaluate(
                        """(i) => {
                            const row = document.querySelectorAll('tr.x-grid-row')[i];
                            if (!row) return null;
                            const cell = row.querySelector('td.x-grid-cell-gridcolumn-1069');
                            return cell ? cell.textContent.trim() : null;
                        }""",
                        idx,
                    )
                except Exception:
                    fname = None
                if fname and fname in seen:
                    continue

                if not await self._click_row_checkbox(page, idx):
                    logging.error("%s – checkbox on row %s not clickable", self.source_type, idx)
                    continue

                await page.wait_for_timeout(300) 

                # trigger download ------------------------------------------------------
                try:
                    async with page.expect_download(timeout=30_000) as dl_ctx:
                        triggered = await page.evaluate("""
                            () => {
                                try {
                                    const tp = Ext.ComponentQuery.query('tabpanel')[0];
                                    if (!tp) return false;
                                    const tab = tp.getActiveTab();
                                    if (!tab || typeof tab.down !== 'function') return false;

                                    // Prefer single-action Download (avoids broken split-button menu)
                                    let btn = tab.down("button[text=Pobierz]") || tab.down("button[text=Download]");
                                    if (btn && btn.handler) {
                                        btn.handler.call(btn.scope || btn);
                                        return true;
                                    }

                                    // Fallback: old split button ‘Download files’ with menu
                                    btn = tab.down("button[text=Pobierz paczkę]") || tab.down("button[text=Download files]");
                                    if (!btn) return false;

                                    btn.showMenu();
                                    const mi = Ext.ComponentQuery.query('menuitem').find(m =>
                                        m.text === 'Pobierz wybrane załączniki' ||
                                        m.text === 'Download selected attachments'
                                    );
                                    if (mi && mi.handler) {
                                        mi.handler.call(mi.scope || mi);
                                        return true;
                                    }
                                    return false;
                                } catch (_) {
                                    return false;
                                }
                            }
                        """)
                        if not triggered:
                            await self._click_row_checkbox(page, idx)  # untick
                            continue
                except Exception as e:
                    if await self._popup_denies_access(page):
                        logging.info("%s – access popup detected, skipping tender %s", self.source_type, details_url)
                        await self._dismiss_popup(page)
                        break  # stop processing this tender entirely
                    # otherwise: normal timeout → continue with next row
                    await self._click_row_checkbox(page, idx)
                    logging.error(
                        f"[Eb2bTenderExtractor] Error downloading file {idx} for {details_url}: {str(e)}"
                    )
                    continue
                download = await dl_ctx.value
                suggested = download.suggested_filename or f"att_{idx}"
                if suggested in seen:
                    await self._click_row_checkbox(page, idx)
                    await page.wait_for_timeout(200)
                    continue
                seen.add(suggested)
                fpath = tmp_root / suggested
                await download.save_as(str(fpath))

                for fcontent, real_name, preview, original_bytes, _orig in await extraction_service.process_file_async(fpath):
                    processed.append((fcontent, real_name, "", preview, original_bytes))

                await self._click_row_checkbox(page, idx)  # untick for cleanliness
                await page.wait_for_timeout(300)

        except Exception as e:
            logging.error(
                f"[Eb2bTenderExtractor] Error opening detail page for file extraction {details_url}: {str(e)}"
            )

        finally:
            await page.close()
            shutil.rmtree(tmp_root, ignore_errors=True)

        return processed

    
    async def find_updates(
        self,
        tenders_to_monitor: List[TenderAnalysisResult]
    ) -> Dict[str, List[Tuple[str, bytes, str, str]]]:
        """
        Check each tender in tenders_to_monitor for new attachments whose
        'Data przesłania' is newer than the tender's last updated_at
        (or created_at if updated_at is None). Download only those new attachments
        by checking their checkboxes, then using "Pobierz wybrane załączniki organizatora".

        Returns:
            Dict[tender_id_str, List[(filename, file_content, file_url)]]
        """
        updates_found: Dict[str, List[Tuple[str, bytes, str, str]]] = {}
        logging.info(f"Starting find_updates for {len(tenders_to_monitor)} tenders to monitor.")

        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        unique_run_id = str(uuid4())
        base_temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_run_id
        base_temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()

                for tender in tenders_to_monitor:
                    last_known_dt = tender.updated_at or tender.created_at
                    # Skip if there's no date to compare
                    if not last_known_dt:
                        logging.warning(
                            f"Skipping tender {tender.id} because it has no updated_at or created_at."
                        )
                        continue

                    logging.info(f"Checking attachments for tender {tender.id} at {tender.tender_url}")
                    detail_page = await context.new_page()

                    try:
                        await self._goto_with_retry(detail_page, tender.tender_url, timeout=60000)
                        await detail_page.wait_for_load_state("networkidle")

                        await self._accept_cookies_if_present(detail_page)
                        await detail_page.wait_for_selector("table.x-grid-table", state="visible", timeout=30000)

                        # Switch to 'Załączniki organizatora' tab
                        logging.info(f"Tender {tender.id}: Activating 'Załączniki organizatora' tab.")
                        success_tab = await detail_page.evaluate("""
                    () => new Promise((resolve) => {
                        try {
                            const tabPanel = Ext.ComponentQuery.query('tabpanel')[0];
                            if (!tabPanel) return resolve(false);
                            const attachTab = tabPanel.items.items.find(tab => (tab.title === 'Załączniki organizatora' || tab.title === "Sponsor's attachments"));
                            if (!attachTab) return resolve(false);
                            const renderListener = {
                                afterrender: function() {
                                    attachTab.un('afterrender', renderListener.afterrender);
                                    setTimeout(() => resolve(true), 1000);
                                },
                                single: true
                            };
                            attachTab.on('afterrender', renderListener.afterrender);
                            tabPanel.setActiveTab(attachTab);
                            setTimeout(() => resolve(false), 10000);
                        } catch (e) {
                            resolve(false);
                        }
                    })
                """)
                        if not success_tab:
                            logging.error(
                                f"Tender {tender.id}: Failed to activate attachments tab."
                            )
                            continue

                        await detail_page.wait_for_timeout(2000)

                        # Check if attachments grid is present
                        new_grid_count = await detail_page.evaluate(
                            "() => document.querySelectorAll('table.x-grid-table').length"
                        )
                        if new_grid_count < 1:
                            logging.warning(
                                f"Tender {tender.id}: No attachments grid found after tab activation."
                            )
                            continue

                        # Evaluate which rows are "new" (Data przesłania > last_known_dt)
                        # await detail_page.wait_for_timeout(20000)

                        logging.info(f"Tender {tender.id}: Checking row dates against {last_known_dt}.")
                        rows_to_check = await detail_page.evaluate(f"""
                            () => {{
                                const parseDate = (dateStr) => {{
                                    try {{
                                        const [ymd, hms] = dateStr.split(' ');
                                        const [yyyy, mm, dd] = ymd.split('-').map(x => parseInt(x,10));
                                        const [HH, MM, SS] = hms.split(':').map(x => parseInt(x,10));
                                        return new Date(dateStr);
                                    }} catch(e) {{
                                        return null;
                                    }}
                                }};
                                const lastKnownDate = new Date("{last_known_dt}");
                                const gridRows = document.querySelectorAll('tr.x-grid-row');
                                const newRowIndexes = [];

                                gridRows.forEach((row, rowIndex) => {{
                                    const dateTd = row.querySelector('td.x-grid-cell-gridcolumn-1084 ');
                                    if (!dateTd) return;
                                    const rawDate = dateTd.innerText.trim();  
                                    if (!rawDate) return;
                                    const dt = parseDate(rawDate);
                                    if (!dt) return;

                                    lastKnownDate.setHours(0,0,0,0);
                                    dt.setHours(0,0,0,0)
                                    
                                    if (dt.getTime() > lastKnownDate.getTime() ) {{
                                        newRowIndexes.push(rowIndex);
                                    }}
                                }});
                                return newRowIndexes;
                            }}
                        """)

                        if not rows_to_check:
                            logging.info(
                                f"Tender {tender.id}: No new attachments found."
                            )
                            continue

                        print(rows_to_check)

                        logging.info(
                            f"Tender {tender.id}: Found {len(rows_to_check)} new attachment(s)."
                        )

                        # Select each row's checkbox
                        for row_idx in rows_to_check:
                            logging.info(
                                f"Tender {tender.id}: Checking row index {row_idx} for download."
                            )
                            # Use a Playwright locator:
                            row_checker_locator = detail_page.locator(
                                "tr.x-grid-row"
                            ).nth(row_idx).locator(
                                "td.x-grid-cell-row-checker div.x-grid-row-checker"
                            )
                            # Ensure the locator is visible, then click
                            await row_checker_locator.wait_for(state="visible", timeout=5000)
                            # If there's any overlay or offset, you can add force=True or set a small delay:
                            await row_checker_locator.click(force=True)
                            # If needed, you can add .hover() or extra steps

                        await detail_page.wait_for_timeout(2000)

                        # Show menu: "Pobierz paczkę" -> "Pobierz wybrane załączniki organizatora"
                        logging.info(
                            f"Tender {tender.id}: Opening 'Pobierz paczkę' menu to download selected attachments."
                        )
                        show_menu_result = await detail_page.evaluate("""
                            () => {
                                try {
                                    const activeTab = Ext.ComponentQuery.query('tabpanel')[0].getActiveTab();
                                    if (!activeTab) return {error: 'No active tab found'};
                                    let downloadBtn = activeTab.down('button[text=Pobierz paczkę]');
                                    if (!downloadBtn) {
                                        downloadBtn = activeTab.down('button[text=Download files]');         
                                        if (!downloadBtn) {     
                                            return {error: 'Download button not found'};
                                        }
                                    }
                                    downloadBtn.showMenu();
                                    return {success: true};
                                } catch (e) {
                                    return {error: e.toString()};
                                }
                            }
                        """)
                        if show_menu_result.get("error"):
                            logging.error(
                                f"Tender {tender.id}: Error showing 'Pobierz paczkę' menu -> {show_menu_result['error']}"
                            )
                            continue

                        await detail_page.wait_for_timeout(1000)

                        # Initiate "Pobierz wybrane załączniki organizatora"
                        try:
                            async with detail_page.expect_download(timeout=30000) as dl_info:
                                pick_selected_result = await detail_page.evaluate("""
                                    () => {
                                        try {
                                            const menuItems = Ext.ComponentQuery.query('menuitem');
                                            const selectedItem = menuItems.find(
                                                item => (item.text === 'Pobierz wybrane załączniki' || item.text === 'Download selected attachments')
                                            );
                                            if (selectedItem && selectedItem.handler) {
                                                selectedItem.handler.call(selectedItem.scope || selectedItem);
                                                return true;
                                            }
                                            return false;
                                        } catch (e) {
                                            return false;
                                        }
                                    }
                                """)
                                if not pick_selected_result:
                                    logging.error(
                                        f"Tender {tender.id}: Could not initiate 'Pobierz wybrane'."
                                    )
                                    continue

                            # Obtain the downloaded file
                            download = await dl_info.value
                            zip_filename = download.suggested_filename or "new_attachments.zip"

                            tender_temp_dir = base_temp_dir / f"{tender.id}"
                            tender_temp_dir.mkdir(parents=True, exist_ok=True)
                            zip_path = tender_temp_dir / zip_filename

                            logging.info(
                                f"Tender {tender.id}: Downloading ZIP to {zip_path}"
                            )
                            await download.save_as(str(zip_path))

                            # Extract the ZIP
                            file_results = await extraction_service.process_file_async(zip_path)
                            # file_results -> List[Tuple[bytes, str]] => (content, filename)
                            # Build final structure
                            attachments = [
                                (file_content, filename, "", preview_chars, original_bytes)
                                for (file_content, filename, preview_chars, original_bytes, original_filename) in file_results
                            ]
                            updates_found[str(tender.id)] = attachments
                            logging.info(
                                f"Tender {tender.id}: Successfully extracted {len(attachments)} new file(s)."
                            )

                        except Exception as e:
                            logging.error(
                                f"Tender {tender.id}: Error during partial attachments download: {e}"
                            )
                            continue

                    finally:
                        await detail_page.close()

                logging.info("Closing browser after checking all tenders.")
                await browser.close()

        finally:
            logging.info(f"Cleaning up temp directory: {base_temp_dir}")
            if base_temp_dir.exists():
                shutil.rmtree(base_temp_dir, ignore_errors=True)

        logging.info("find_updates completed.")
        return updates_found