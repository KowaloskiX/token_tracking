from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
from uuid import uuid4

from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender
from minerva.core.services.vectorstore.file_content_extract.service import (
    FileExtractionService,
)
from playwright.async_api import async_playwright, BrowserContext, Page, TimeoutError


# ──────────────────────────────────────────────────────────────────────────────
#  default root-url → source_type mapping
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_PAGE_TYPE_MAP: dict[str, str] = {
    "https://www.tender24.de/NetServer/": "vergabeplatforms_tender24",
    "https://vergabeplattform.bwb.de/NetServer/": "vergabeplatforms_bwb",
    "https://vergabeplattform.stadt-koeln.de/NetServer/": "vergabeplatforms_stadt",
    "https://vergabeplattform.smaby.de/NetServer/": "vergabeplatforms_smaby",
    "https://saarvpsl.vmstart.de/NetServer/": "vergabeplatforms_saarvpsl",
    "https://lhs-vpbw.vmstart.de/NetServer/": "vergabeplatforms_lhs_vpbw",
    "https://vergabe.vmstart.de/NetServer/": "vergabeplatforms_vmstart",
    "https://vergabe.lvr.de/NetServer/": "vergabeplatforms_lvr",
    "https://vergabe.bremen.de/NetServer/": "vergabeplatforms_bremen",
    "https://vergabe.autobahn.de/NetServer/": "vergabeplatforms_autobahn",
    "https://vergabeplattform.ai-ilv.de/NetServer/": "vergabeplatforms_ai_ilv",
    "https://beschaffungen.barmer.de/NetServer/": "vergabeplatforms_barmer",
    "https://ibsh-vp-prod.ai-hosting.de/NetServer/": "vergabeplatforms_ibsh",
    "https://vergabe.uksh.de/NetServer/": "vergabeplatforms_uksh",
    "https://www.evergabe.sachsen.de/NetServer/": "vergabeplatforms_sachsen",
    "https://ausschreibung.halle.de/NetServer/": "vergabeplatforms_halle",
    "https://vergabe.saarland/NetServer/": "vergabeplatforms_saarland",
    "https://vergabe.duesseldorf.de/NetServer/": "vergabeplatforms_duesseldorf",
    "https://vergabe.fraunhofer.de/NetServer/": "vergabeplatforms_fraunhofer",
    "https://vergabe.lvr.de/NetServer/": "vergabeplatforms_lvr",
    "https://vergabe.vmstart.de/NetServer/": "vergabeplatforms_vmstart",
    "https://vergabemarktplatz-mv.de/NetServer/": "vergabeplatforms_vergabemarktplatz_mv",
}


# ══════════════════════════════════════════════════════════════════════════════
class VergabePlatformsTenderExtractor:
    # --------------------------------------------------------------------- init
    def __init__(
        self,
        page_type_map: Optional[dict[str, str]] = None,
        fallback_source_type: str = "vergabeplatforms",
    ):
        """
        Parameters
        ----------
        page_type_map
            Mapping {root_url → source_type}.  
            • *None*  ⇒ use DEFAULT_PAGE_TYPE_MAP.  
            • Dict()  ⇒ exactly what you supply.

        fallback_source_type
            Used only if a root URL is not present in `page_type_map`.
        """
        self.page_type_map: dict[str, str] = (
            page_type_map if page_type_map is not None else DEFAULT_PAGE_TYPE_MAP
        )
        self.root_pages: List[str] = list(self.page_type_map.keys())
        self._fallback_source_type = fallback_source_type
        self.source_type: str = fallback_source_type
        # Add URL tracking
        self.url_tracking = {}  # source_type -> set of URLs
        self.unique_urls = set()  # Track all unique URLs across all sources

    # ───────────────────────────── helpers ──────────────────────────────
    async def _goto_with_retry(
        self,
        page: Page,
        url: str,
        wait_until: str = "networkidle",
        timeout: int = 30_000,
        retries: int = 2,
    ):
        for attempt in range(retries + 1):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return
            except Exception as e:
                if "Timeout" in str(e) and attempt < retries:
                    logging.info(f"[{self.source_type}] retry {attempt+1}: {url}")
                else:
                    logging.error(f"[{self.source_type}] load failed: {url}: {e}")
                    raise

    @staticmethod
    def _std_date(raw: str) -> str:
        """dd.mm.yyyy  →  yyyy-mm-dd"""
        try:
            return datetime.strptime(raw.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
        except Exception:
            return ""

    @staticmethod
    def _std_datetime(raw: str) -> str:
        """dd.mm.yyyy HH:MM  →  yyyy-mm-dd HH:MM:00"""
        try:
            return datetime.strptime(raw.strip(), "%d.%m.%Y %H:%M").strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except Exception:
            return ""

    # ─────────────────────────── detail page ────────────────────────────
    async def _fetch_detail_info(self, context: BrowserContext, detail_url: str) -> dict:
        """
        Returns
        -------
        {"location": <city>, "skip": True/False}

        * skip = True  →  listing loop must ignore this tender (no files).
        * location is parsed by REGEX from plain text.
        """
        info = {"location": "", "skip": False}
        page = await context.new_page()

        try:
            await self._goto_with_retry(page, detail_url)

            # must have downloadDocuments link
            if not await page.query_selector(
                "div.downloadDocuments a[href*='TenderingProcedureDetails'][href*='function=_Details']"
            ):
                info["skip"] = True
                return info

            txt = (await page.inner_text("body")).replace("\r", "\n").strip()
            m = re.search(
                r"Postleitzahl\s*/?\s*Ort\s*:?\s*\d{4,5}\s+([A-Za-zÄÖÜäöüß\- ]{2,})",
                txt,
                flags=re.I,
            )
            if m:
                info["location"] = m.group(1).strip()

        except Exception as e:
            logging.error(f"[{self.source_type}] detail error {detail_url}: {e}")
        finally:
            await page.close()

        return info

    # ────────────────────────── main listing ────────────────────────────
    async def execute(self, inputs: Dict) -> Dict:
        max_pages = inputs.get("max_pages", 50)
        start_dt = (
            datetime.strptime(inputs["start_date"], "%Y-%m-%d").date()
            if inputs.get("start_date")
            else None
        )

        tenders: List[Tender] = []
        pages_visited = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()

                for root in self.root_pages:
                    pages_visited = 0
                    self.source_type = self.page_type_map.get(
                        root, self._fallback_source_type
                    )
                    # Initialize URL tracking for this source type
                    self.url_tracking[self.source_type] = set()
                    
                    logging.info(f"[{self.source_type}] Processing root: {root}")
                    tenders_before = len(tenders)

                    page = await context.new_page()

                    try:
                        await self._goto_with_retry(page, root)
                    except Exception as e:
                        logging.error(f"Error loading page: {root} {e}")
                        continue
                    # link to publication search
                    more_link = await page.query_selector(
                        "div.page a[href*='PublicationSearchControllerServlet'][href*='Category=InvitationToTender']"
                    )
                    if not more_link:
                        more_link = await page.query_selector(
                            "body a[href*='PublicationSearchControllerServlet'][href*='Category=InvitationToTender']"
                        )
                        if not more_link:
                            logging.warning(
                                f"[{self.source_type}] publication search link missing on {root}"
                            )
                            await page.close()
                            continue

                    listing_url = urljoin(root, await more_link.get_attribute("href"))
                    await self._goto_with_retry(page, listing_url)
                    base_prefix = listing_url.split("PublicationSearchControllerServlet")[0]

                    # paginate
                    stop_root = False
                    while (
                        pages_visited < max_pages
                        and not stop_root
                        and await page.query_selector("tbody tr.tableRow")
                    ):
                        pages_visited += 1
                        rows = await page.query_selector_all(
                            "tbody tr.tableRow.publicationDetail"
                        )

                        # column index mapping
                        headers = await page.query_selector_all("thead th.tabelleFirstLine")
                        cols = {"pub_date": None, "name": None, "org": None, "deadline": None}
                        for i, h in enumerate(headers):
                            t = (await h.inner_text()).lower()
                            if "erschienen" in t:
                                cols["pub_date"] = i
                            elif "ausschreibung" in t:
                                cols["name"] = i
                            elif "vergabestelle" in t:
                                cols["org"] = i
                            elif "abgabefrist" in t:
                                cols["deadline"] = i

                        for row in rows:
                            cells = await row.query_selector_all("td")
                            if (
                                len(cells)
                                < max(i for i in cols.values() if i is not None) + 1
                            ):
                                continue

                            pub_date = datetime.strptime(
                                (await cells[cols["pub_date"]].inner_text()).strip(),
                                "%d.%m.%Y",
                            ).date()
                            if start_dt and pub_date < start_dt:
                                stop_root = True
                                break

                            name = (await cells[cols["name"]].inner_text()).strip()
                            deadline_std = self._std_datetime(
                                (await cells[cols["deadline"]].inner_text()).strip()
                            )
                            org_on_row = (
                                (await cells[cols["org"]].inner_text()).strip()
                                if cols["org"] is not None
                                else ""
                            )
                            oid = (await row.get_attribute("data-oid")).strip()
                            if self.source_type == "vergabeplatforms_fraunhofer":
                                anchor = await row.query_selector("td.tender a")
                                if anchor:
                                    detail_url = await anchor.get_attribute("href")
                                    detail_url = root + detail_url
                                    # Track URL
                                    self.url_tracking[self.source_type].add(detail_url)
                                    if detail_url not in self.unique_urls:
                                        self.unique_urls.add(detail_url)
                                    logging.info(f"[{self.source_type}] Extracted detail URL from anchor: {detail_url}")
                                else:
                                    logging.error(f"[{self.source_type}] Could not find anchor tag in tender row")
                                    continue
                            else:
                                detail_url = (
                                    f"{base_prefix}PublicationControllerServlet?"
                                    f"function=Detail&TOID={oid}&Category=InvitationToTender"
                                )
                                # Track URL
                                self.url_tracking[self.source_type].add(detail_url)
                                if detail_url not in self.unique_urls:
                                    self.unique_urls.add(detail_url)

                            extra = await self._fetch_detail_info(context, detail_url)
                            if extra["skip"]:
                                continue

                            try:
                                tenders.append(
                                    Tender(
                                        name=name,
                                        organization=org_on_row,
                                        location=extra["location"],
                                        submission_deadline=deadline_std,
                                        initiation_date=pub_date.strftime("%Y-%m-%d"),
                                        details_url=detail_url,
                                        content_type="tender",
                                        source_type=self._fallback_source_type,
                                    )
                                )
                                logging.info(f"{self.source_type}: scraped tender '{name}'")
                            except Exception as e:
                                logging.error(
                                    f"[{self.source_type}] Tender object failed: {e}"
                                )

                        # next page
                        if stop_root or pages_visited >= max_pages:
                            break
                        nxt = await page.query_selector(
                            "ul.pagination li a[title='Next Page']"
                        )
                        if nxt:
                            await nxt.click()
                            await page.wait_for_load_state("networkidle")
                        else:
                            break

                    await page.close()
                    # Log tenders scraped for this source type
                    tenders_after = len(tenders)
                    tenders_scraped = tenders_after - tenders_before
                    logging.info(f"[{self.source_type}] Scraped {tenders_scraped} tenders from {root}")

                meta = ExtractorMetadata(
                    total_tenders=len(tenders), pages_scraped=pages_visited
                )
                # Log summary of tenders per source type
                source_type_counts = {}
                for tender in tenders:
                    source_type_counts[tender.source_type] = source_type_counts.get(tender.source_type, 0) + 1
                for source_type, count in source_type_counts.items():
                    logging.info(f"[{source_type}] Total tenders scraped: {count}")

                # Print URL tracking summary
                logging.info("=== URL Tracking Summary ===")
                for source_type, urls in self.url_tracking.items():
                    total_urls = len(urls)
                    unique_urls = sum(1 for url in urls if url in self.unique_urls)
                    duplicate_urls = total_urls - unique_urls
                    logging.info(f"Source Type: {source_type}")
                    logging.info(f"Total URLs: {total_urls}")
                    logging.info(f"Unique URLs: {unique_urls}")
                    logging.info(f"Duplicate URLs: {duplicate_urls}")
                logging.info(f"Total unique URLs across all sources: {len(self.unique_urls)}")
                logging.info("========================\n")

                return {"tenders": tenders, "metadata": meta}
            
            except Exception as e:
                logging.error(f"Error scraping {self._fallback_source_type}: {e}")
                return {"tenders": tenders, "metadata": ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=pages_visited,)
                    }
            finally:
                await browser.close()

    # ───────────────────────── file download (one-by-one) ────────────────────────────
    async def extract_files_from_detail_page(  # noqa: C901
        self,
        context: BrowserContext,
        details_url: str,
    ) -> List[Tuple[bytes, str, Optional[str]]]:
        """
        Downloads every attachment from the “Vergabeunterlagen” modal **one at a time**
        (no bulk ZIP download).
        """
        MAX_MODAL_RETRIES = 3
        MODAL_WAIT_TIMEOUT = 10_000  # ms

        page = await context.new_page()
        processed_files: List[Tuple[bytes, str, Optional[str]]] = []
        service = FileExtractionService()
        temp_dir: Optional[Path] = None

        async def _get_latest_zip_button() -> Optional[Page]:
            """
            Unchanged helper: finds the row whose timestamp (2nd <td>) is newest and
            returns its “Unterlagen … herunterladen” button (opens the modal).
            """
            try:
                await page.wait_for_selector(
                    "table.table-striped.tableQuarter.table-hover.table-center tbody tr",
                    timeout=5_000,
                )
            except TimeoutError:
                return None

            rows = await page.query_selector_all(
                "table.table-striped.tableQuarter.table-hover.table-center tbody tr"
            )
            newest_row, newest_dt = None, datetime.min
            for r in rows:
                try:
                    txt = (
                        await (await r.query_selector("td:nth-child(2) span")).inner_text()
                    ).strip()
                    dt_val = datetime.strptime(txt, "%d.%m.%Y %H:%M")
                    if dt_val > newest_dt:
                        newest_dt, newest_row = dt_val, r
                except Exception:
                    continue
            return None if not newest_row else await newest_row.query_selector(
                "a.btn-modal.zipFileContents"
            )

        async def _open_modal() -> bool:
            """Try up to MAX_MODAL_RETRIES times to open the modal and wait for it."""
            for attempt in range(1, MAX_MODAL_RETRIES + 1):
                zip_btn = await _get_latest_zip_button()
                if not zip_btn:
                    return False
                await zip_btn.click()
                try:
                    await page.wait_for_selector(
                        ".modal-content .fileDownload",
                        state="visible",
                        timeout=MODAL_WAIT_TIMEOUT,
                    )
                    return True  # success
                except TimeoutError:
                    if attempt == MAX_MODAL_RETRIES:
                        return False
                    await page.reload()
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(500)
            return False

        try:
            # 1) open details page
            await self._goto_with_retry(page, details_url)

            # 2) click “Unterlagen zur Ansicht herunterladen”
            dl_link = await page.query_selector(
                "div.downloadDocuments a:has-text('Unterlagen zur Ansicht herunterladen')"
            )
            if not dl_link:
                return []

            await dl_link.click()
            await page.wait_for_load_state("networkidle")

            # 3) open the modal (with retry)
            if not await _open_modal():
                return []

            # 4) iterate over EVERY file link inside the modal
            file_links = await page.query_selector_all(".modal-content a.filenameEllipsis")
            if not file_links:
                return []

            temp_dir = Path.cwd() / "temp_files" / uuid4().hex
            temp_dir.mkdir(parents=True, exist_ok=True)

            for idx, link in enumerate(file_links, 1):
                # The visible filename is fine; duplicates are prefixed with idx
                visible_name = (await link.inner_text()).strip()

                async with page.expect_download() as dl_info:
                    await link.click()  # opens “_blank” → download starts
                download = await dl_info.value

                out_path = temp_dir / visible_name
                if out_path.exists():  # guard against identical names
                    out_path = temp_dir / f"{idx}_{visible_name}"
                await download.save_as(str(out_path))

                # Delegate to your service – unchanged
                for (
                    file_content,
                    extracted_name,
                    preview_chars,
                    original_bytes,
                    original_filename,
                ) in await service.process_file_async(out_path):
                    processed_files.append(
                        (
                            file_content,
                            extracted_name,
                            download.url,
                            preview_chars,
                            original_bytes,
                        )
                    )

        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            await page.close()

        return processed_files
