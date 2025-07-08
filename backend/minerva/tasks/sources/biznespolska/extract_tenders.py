from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# Generic tender model (identical to Oferent extractor)
# ---------------------------------------------------------------------------

class Tender(BaseModel):
    name: str = ""
    organization: str = ""
    location: str = ""
    submission_deadline: Optional[str] = ""
    initiation_date: Optional[str] = ""
    details_url: str = ""
    content_type: str = "tender"
    source_type: str = "biznes‑polska"

    # Biznes‑Polska specific
    tender_id: str = ""
    region: str = ""
    added_date: Optional[str] = ""
    client: Dict[str, Any] = Field(default_factory=dict)
    submission_info: Dict[str, Any] = Field(default_factory=dict)
    external_urls: List[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ExtractorMetadata(BaseModel):
    total_tenders: int
    pages_scraped: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DateStandardizer:
    """Utility class that converts many display formats to ISO yyyy‑mm‑dd."""

    _pat = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})")

    @classmethod
    def iso(cls, text: str) -> str:
        if not text:
            return ""
        m = cls._pat.search(text)
        if not m:
            return text.strip()
        day, month, year = map(int, m.groups())
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return text.strip()


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

class BiznesPolskaReportExtractor:  # pylint: disable=too-many-public-methods
    """Extractor for https://www.biznes‑polska.pl daily/periodic profile reports."""

    base_url = "https://www.biznes-polska.pl"

    #: External procurement platforms worth surfacing (same list as Oferent + a few extras)
    source_platforms = [
        "ezamowienia.gov.pl",
        "ted.europa.eu",
        "egospodarka.pl",
        "eb2b.com.pl",
        "ezamawiajacy.pl",
        "logintrade.pl",
        "smartpzp.pl",
        "epropublico.pl",
        "platformazakupowa.pl",
        "bazakonkurencyjnosci.funduszeeuropejskie.gov.pl",
        "connect.orlen.pl",
        "pge.pl",
    ]

    procurement_platforms = source_platforms  # alias for readability

    # ---------------------------------------------------------------------
    # Low‑level page helpers
    # ---------------------------------------------------------------------

    async def _goto_with_retry(self, page, url: str, *, wait_until: str = "networkidle", timeout: int = 15_000):
        for attempt in range(3):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return
            except Exception as exc:  # noqa: BLE001
                logging.warning("Navigate attempt %s failed for %s: %s", attempt + 1, url, exc)
                if attempt == 2:
                    raise
                await page.wait_for_timeout(1_500)

    # ------------------------------------------------------------------
    # URL extraction and classification (shared with Oferent logic)
    # ------------------------------------------------------------------

    _url_regex = re.compile(
        r"https?://(?:[-\w.]|(?:%[0-9A-Fa-f]{2}))+(?:/[-\w%!$&'()*+,;=:@/~]+)*(?:\?[\w%!$&'()*+,;=:@/~]*)?(?:#[\w%!$&'()*+,;=:@/~]*)?"
    )

    def _extract_urls(self, html: str) -> List[str]:
        urls = self._url_regex.findall(html)
        filtered: list[str] = []
        for url in urls:
            if url.endswith((".js", ".css", ".jpg", ".png", ".svg")) or "mailto:" in url:
                continue
            if any(p in url for p in self.source_platforms):
                filtered.append(url)
            elif re.match(r"https?://[-\w.]+\.[a-z]{2,}/", url):
                filtered.append(url)
        return list(dict.fromkeys(filtered))  # keep order, drop dups

    def _detect_source(self, urls: List[str], html: str) -> str:
        for url in urls:
            for p in self.procurement_platforms:
                if p in url:
                    return p
        for p in self.procurement_platforms:
            if p in html:
                return p
        if "BZP" in html or "Biuletyn Zamówień Publicznych" in html:
            return "ezamowienia.gov.pl"
        return "biznes‑polska"

    # ------------------------------------------------------------------
    # Detail page scraping
    # ------------------------------------------------------------------

    async def _scrape_detail(self, context, url: str) -> Optional[Dict[str, Any]]:  # noqa: C901, PLR0915
        """Populate a Tender dict from its Biznes‑Polska detail page."""
        page = await context.new_page()
        page.set_default_timeout(15_000)
        try:
            # print(url)
            await self._goto_with_retry(page, url)
            await page.wait_for_timeout(500)  # wait for page to load

            await page.wait_for_selector("article.offer-sheet", timeout=10_000)
            html_full = await page.content()

            # print(html_full[:200])

            tender: Dict[str, Any] = {
                "tender_id": "",
                "name": "",
                "organization": "",
                "location": "",
                "submission_deadline": "",
                "initiation_date": "",
                "details_url": url,
                "content_type": "tender",
                "source_type": "biznes‑polska",
                "region": "",
                "added_date": "",
                "client": {
                    "name": "",
                    "address": "",
                    "region": "",
                    "district": "",
                    "phone": "",
                    "email": "",
                    "website": "",
                },
                "submission_info": {
                    "place": "",
                    "deadline": "",
                    "text": "",
                },
                "external_urls": [],
            }

            # --- grab table rows -------------------------------------------------
            rows = await page.query_selector_all("article.offer-sheet table tr")
            for row in rows:
                th = await row.query_selector("th")
                td = await row.query_selector("td")
                if not (th and td):
                    continue
                key = (await th.inner_text()).strip().lower()
                val_html = await td.inner_html()
                val_text = (await td.inner_text()).strip()

                if "numer ogłoszenia" in key:
                    tender["tender_id"] = val_text
                elif "przedmiot ogłoszenia" in key:
                    tender["name"] = re.sub(r"\s+", " ", val_text)
                elif "organizator" in key:
                    tender["organization"] = val_text
                    tender["client"]["name"] = val_text
                elif "adres" in key:
                    tender["client"]["address"] = re.sub(r"\s+", " ", val_text)
                elif "województwo" in key:
                    parts = [p.strip() for p in val_text.split(",")]
                    if parts:
                        tender["region"] = parts[0]
                        tender["client"]["region"] = parts[0]
                        if len(parts) > 1:
                            tender["client"]["district"] = parts[1]
                elif "data dodania" in key:
                    tender["added_date"] = val_text
                    tender["initiation_date"] = DateStandardizer.iso(val_text)
                elif "e-mail" in key:
                    m = re.search(r"[\w.+-]+@[\w.-]+", val_text)
                    tender["client"]["email"] = m.group(0) if m else val_text
                elif "termin składa" in key and "ofert" in key:
                    # row 'Miejsce i termin składania ofert:' has nested text
                    deadline_match = re.search(r"(\d{4}-\d{2}-\d{2})", val_text)
                    if deadline_match:
                        tender["submission_deadline"] = deadline_match.group(1)
                    tender["submission_info"]["text"] = val_text
                elif "strona www" in key:
                    link = await td.query_selector("a")
                    if link:
                        href = await link.get_attribute("href")
                        if href:
                            tender["client"]["website"] = href

                # fallback: urls extraction
                ext_urls = self._extract_urls(val_html)
                if ext_urls:
                    tender.setdefault("external_urls", []).extend(ext_urls)

            if not tender["external_urls"]:
                tender["external_urls"] = self._extract_urls(html_full)
            tender["external_urls"] = list(dict.fromkeys(tender["external_urls"]))

            # infer source
            tender["source_type"] = self._detect_source(tender["external_urls"], html_full)

            # build location string if missing
            if not tender["location"] and tender["client"].get("region"):
                loc_parts = [tender["client"].get("region"), tender["client"].get("district"), tender["client"].get("address")]
                tender["location"] = " / ".join(p for p in loc_parts if p)
        
            return tender
        finally:
            await page.close()

    # ------------------------------------------------------------------
    # Listing extraction – called after report preview is displayed
    # ------------------------------------------------------------------

    async def _extract_listing_urls(self, page) -> List[str]:
        """Return canonical detail URLs for *Przetargi* only.

        Handles both internal fragment anchors (``#offer‑<id>`` or
        ``name="spis-<id>"``) and occasional full links that already contain
        ``/przetargi/<id>/``.
        """
        script = """
        () => {
          const ids = new Set();
          const stopIds = ['inwestycje', 'sprzedaz', 'sprzedaż', 'zlecenia', 'wyniki', 'kupno'];
          const startRow = document.querySelector('tr#przetargi');
          if (!startRow) { return []; }
          let node = startRow.nextElementSibling;
          while (node) {
            if (node.id && stopIds.includes(node.id.toLowerCase())) { break; }
            node.querySelectorAll('a').forEach(a => {
              const name = a.getAttribute('name') || '';
              const href = a.getAttribute('href') || '';
              let match;
              if (name.startsWith('spis-')) {
                ids.add(name.slice(5));
              } else if ((match = href.match(/^#?offer-(\d+)/))) {
                ids.add(match[1]);
              } else if ((match = href.match(/\/przetargi\/(\d+)/))) {
                ids.add(match[1]);
              }
            });
            node = node.nextElementSibling;
          }
          return Array.from(ids);
        }
        """
        raw_ids: List[str] = await page.evaluate(script)
        return [f"{self.base_url}/przetargi/{tid}" for tid in raw_ids]

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:  # noqa: C901, PLR0911
        """Run the whole extraction flow and return {tenders, metadata}."""
        username = inputs.get("username")
        password = inputs.get("password")
        profile_name = inputs.get("profile_name")
        if not all((username, password, profile_name)):
            raise ValueError("username, password and profile_name are required in inputs")

        date_from = inputs.get("date_from") or datetime.now().strftime("%Y-%m-%d")
        date_to = inputs.get("date_to") or datetime.now().strftime("%Y-%m-%d")
        current_only: bool = inputs.get("current_only", True)

        tenders: list[Tender] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                context = await browser.new_context()
                context.set_default_timeout(15_000)
                page = await context.new_page()

                # ------------------------------------------------------------------
                # Login
                # ------------------------------------------------------------------
                login_url = f"{self.base_url}/logowanie/?next=%2Fpanel%2Fprofile%2F"
                await self._goto_with_retry(page, login_url)
                await page.wait_for_timeout(1_000)  # wait for page to load
                await page.fill("#username", username)
                await page.fill("#password", password)
                await page.wait_for_timeout(500)  # wait for page to load
                # More robust login button click
                login_button = await page.query_selector("button[type=submit][value='Zaloguj']")
                if login_button:
                    await page.evaluate('(btn) => btn.scrollIntoView()', login_button)
                    await login_button.click()
                else:
                    # fallback to previous method if not found
                    await page.click("button[type=submit]")

                # wait for redirect to profile overview
                await page.wait_for_url(f"{self.base_url}/panel/profile/**")

                # ------------------------------------------------------------------
                # Pick the requested profile
                # ------------------------------------------------------------------
                rows = await page.query_selector_all("table.tbl-profiles tr")
                profile_id = None
                for idx, row in enumerate(rows):
                    link = await row.query_selector("a[href*='/edytuj/']")
                    if not link:
                        continue
                    txt = (await link.inner_text()).strip()
                    if txt.lower() == profile_name.lower():
                        # the "row-additional" is the *next* row
                        extra_row = rows[idx + 1] if idx + 1 < len(rows) else None
                        if not extra_row:
                            logging.warning("Could not find additional row for profile %s", profile_name)
                            break
                        preview_link = await extra_row.query_selector("a.report-preview")
                        if not preview_link:
                            logging.warning("Preview link not found for profile %s", profile_name)
                            break
                        href = await preview_link.get_attribute("href")
                        m = re.search(r"/panel/profile/(\d+)/", href or "")
                        profile_id = m.group(1) if m else None
                        await preview_link.click()
                        break
                if not profile_id:
                    raise RuntimeError(f"Profile '{profile_name}' not found under this account.")

                # ------------------------------------------------------------------
                # Configure and submit report preview modal (fancybox content hosted in <form id=report-form>)
                # ------------------------------------------------------------------
                await page.wait_for_selector("#report-form", timeout=10_000)

                # select period_type=4 (custom range)
                await page.check("input[name=period_type][value='4']")
                await page.fill("#period_date_from", date_from)
                await page.fill("#period_date_to", date_to)


                await page.wait_for_timeout(500)  # wait for page to load

                # option: 1 = aktualne, 2 = wszystkie
                await page.check(f"input[name=option][value='{'1' if current_only else '2'}']")

                async with page.expect_navigation():
                    await page.click("#report-form button[type=submit]")

                # ------------------------------------------------------------------
                # Results page – extract listing
                # ------------------------------------------------------------------
                await page.wait_for_timeout(500)  # wait for page to load

                listing_urls = await self._extract_listing_urls(page)
                logging.info("Found %d potential tender urls in listing", len(listing_urls))


                processed_ids: set[str] = set()
                for url in listing_urls:
                    tid = url.rsplit("/", 1)[-1]
                    if tid in processed_ids:
                        continue
                    processed_ids.add(tid)
                    await page.wait_for_timeout(500)  # wait for page to load

                    try:
                        tdata = await self._scrape_detail(context, url)
                        # print(tdata)
                        if not tdata:
                            continue
                        # ensure category says "przetarg" – quick heuristic
                        if "content_type" in tdata and tdata["content_type"] != "tender":
                            continue
                        tender_obj = Tender(**tdata)
                        tenders.append(tender_obj)
                        logging.debug("Processed tender %s", tid)
                    except PlaywrightTimeoutError as e:
                        logging.warning("Timeout while scraping %s: %s", url, e)
                    except Exception as exc:  # noqa: BLE001
                        logging.error("Error scraping %s: %s", url, exc)

                metadata = ExtractorMetadata(total_tenders=len(tenders), pages_scraped=1)
                return {"tenders": tenders, "metadata": metadata}
            finally:
                await browser.close()
