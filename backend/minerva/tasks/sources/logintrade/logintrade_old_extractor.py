import logging
from datetime import datetime
from typing import Dict

from minerva.core.services.vectorstore.pinecone.query import QueryConfig, QueryTool
from playwright.async_api import async_playwright

from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender



class LogintradeOldExtractor:
    """
    A tender extractor for the listing at https://platforma.logintrade.net/platforma-zakupowa,zapytania_otwarte.html
    demonstrating how to:
      - parse the main listing table (.defaultTable)
      - fetch detail info from the tender detail page
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
    

    async def execute_self(self, inputs: Dict) -> Dict:
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
        # Pinecone config (standardized)
        tender_names_index_name = inputs.get('tender_names_index_name', "tenders")
        embedding_model = inputs.get('embedding_model', "text-embedding-3-large")
        pinecone_tool = QueryTool(QueryConfig(index_name=tender_names_index_name, embedding_model=embedding_model))

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

                    stop_extraction = False
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
                            try:
                                if publication_date_str:
                                    publication_dt = datetime.strptime(publication_date_str, "%d.%m.%Y %H:%M")
                            except ValueError:
                                logging.warning(f"Could not parse publication date from '{publication_date_str}'")
                            submission_dt = None
                            try:
                                if submission_date_str:
                                    submission_dt = datetime.strptime(submission_date_str, "%d.%m.%Y %H:%M")
                            except ValueError:
                                logging.warning(f"Could not parse submission date from '{submission_date_str}'")
                            # --- Standardized Pinecone logic for tenders older than start_dt ---
                            if start_dt and publication_dt and (publication_dt < start_dt):
                                try:
                                    if pinecone_tool and detail_url:
                                        filter_conditions = {"details_url": detail_url}
                                        pinecone_result = await pinecone_tool.query_by_id(
                                                id=detail_url,
                                                top_k=1,
                                                filter_conditions=filter_conditions
                                            )
                                        if pinecone_result.get("matches"):
                                            logging.info(f"[LoginTradeTenderExtractor] Found tender in Pinecone, stopping extraction: {detail_url}")
                                            stop_extraction = True
                                            break
                                        else:
                                            logging.info(f"[LoginTradeTenderExtractor] Tender not found in Pinecone, including with initiation_date set to start_dt: {detail_url}")
                                            publication_dt = start_dt
                                    else:
                                        logging.info(f"Skipping older tender '{name}' published at {publication_dt}")
                                        continue
                                except Exception as e:
                                    logging.error(f"[LoginTradeTenderExtractor] Error querying Pinecone for {detail_url}: {str(e)}")
                                    continue
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
                    if stop_extraction:
                        break
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