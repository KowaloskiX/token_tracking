import logging
from datetime import datetime
from typing import Dict

from playwright.async_api import async_playwright

from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender



class LogintradeNetExtractor:
    """
    A tender extractor for the listing at https://platforma.logintrade.net/platforma-zakupowa,zapytania_otwarte.html
    demonstrating how to:
      - parse the main listing table (.defaultTable)
      - fetch detail info from the tender detail page
      - skip tenders older than a given start_date
    """

    def __init__(
        self,
        base_url: str = "https://platforma.logintrade.net/platforma-zakupowa,zapytania_otwarte.html",
        source_type: str = "logintrade"
    ):
        self.base_url = base_url.rstrip("/")
        self.source_type = source_type

        # URL for the listing page
        self.list_url = f"{self.base_url}"

    async def fetch_detail_info(
        self,
        context,
        detail_url: str
    ) -> dict:
        """
        Extract additional info from the detail page, e.g. full name of the organization,
        detailed description, contact information, etc.
        """

        page = await context.new_page()
        detail_info = {
            "org_name": "",
            "full_description": "",
            "contact_info": "",
            "attachments": [],
            "has_attachments": False,
            "attachments_require_login": False
        }

        try:
            await page.goto(detail_url, wait_until='networkidle', timeout=20000)

            # Check for and handle info panel
            info_panel = await page.query_selector("#infoPanel")
            if info_panel:
                logging.info("[LogintradeNetExtractor] Found info panel, clicking OK button")
                ok_button = await page.query_selector("#infoPanel .buttonLogowanie")
                if ok_button:
                    await ok_button.click()
                    # Wait for the panel to disappear and content to be visible
                    await page.wait_for_selector("#container", state="visible", timeout=5000)
                    await page.wait_for_timeout(1000)  # Additional small delay to ensure content is loaded

            # Extracting organization name from firma_info div
            org_section = await page.query_selector("#firma_info")
            if org_section:
                org_name_el = await org_section.query_selector(".firma_nazwa")
                if org_name_el:
                    detail_info["org_name"] = (await org_name_el.inner_text()).strip()

            # Extracting full description from niceEdit_text div
            description_el = await page.query_selector(".niceEdit_text")
            if description_el:
                detail_info["full_description"] = (await description_el.inner_text()).strip()

            # Contact info from dane_osob div
            contact_section = await page.query_selector("#dane_osob")
            if contact_section:
                contact_info_elements = await contact_section.query_selector_all("h3")
                contact_info = []
                for el in contact_info_elements:
                    txt = (await el.inner_text()).strip()
                    if txt:
                        contact_info.append(txt)
                detail_info["contact_info"] = ", ".join(contact_info)

            # Check for attachments
            attachments_section = await page.query_selector("ul.zalaczniki")
            if attachments_section:
                detail_info["has_attachments"] = True
                attachment_links = await attachments_section.query_selector_all("li a")
                attachments = []
                for link in attachment_links:
                    name = (await link.inner_text()).strip()
                    href = await link.get_attribute("href")
                    if href:
                        attachments.append({"name": name, "url": href})
                detail_info["attachments"] = attachments
            else:
                # Check if attachments require login
                login_required = await page.query_selector("p:has-text('Attachments are avalible after log-in')")
                if login_required:
                    detail_info["attachments_require_login"] = True

        except Exception as e:
            logging.error(f"[LogintradeNetExtractor] Error fetching detail info from {detail_url}: {str(e)}")
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
        max_pages = inputs.get("max_pages", 10)
        start_date_str = inputs.get("start_date", None)

        start_dt = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                logging.info(f"[LogintradeNetExtractor] Start date = {start_dt}")
            except ValueError:
                logging.error(f"[LogintradeNetExtractor] Invalid date format for 'start_date': {start_date_str}")

        # Initialize attachment statistics
        attachment_stats = {
            "with_attachments": 0,
            "without_attachments": 0,
            "attachments_require_login": 0
        }

        async with async_playwright() as p:
            # Launch the browser
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()

                logging.info(f"[LogintradeNetExtractor] Navigating to {self.list_url}")
                await page.goto(self.list_url, wait_until='networkidle', timeout=20000)

                tenders = []
                current_page = 1
                while current_page <= max_pages:
                    logging.info(f"[LogintradeNetExtractor] Scraping page {current_page}/{max_pages}...")

                    rows = await page.query_selector_all(".defaultTable tbody tr:not(:first-child)")
                    if not rows:
                        logging.info("[LogintradeNetExtractor] No more rows found; stopping.")
                        break

                    for row in rows:
                        try:
                            # Get all cells in the row
                            columns = await row.query_selector_all("td")
                            
                            # Skip if row doesn't have the expected format
                            if len(columns) < 7:
                                continue

                            # Column 1: Item number (don't need)
                            
                            # Column 2: Enquiry name with link to details
                            name_cell = columns[1]
                            link_element = await name_cell.query_selector("a")
                            
                            if not link_element:
                                continue
                                
                            name = (await link_element.inner_text()).strip()
                            detail_url = await link_element.get_attribute("href") or ""
                            # Ensure URL is absolute
                            if not detail_url.startswith(("http://", "https://")):
                                detail_url = self.base_url + detail_url
                            
                            # Column 3: Date of publication
                            pub_date_cell = columns[2]
                            pub_date_str = (await pub_date_cell.inner_text()).strip()
                            # Handle format "2025-05-16" or "2025-05-16 (updated: 2025-05-16)"
                            if pub_date_str:
                                pub_date_str = pub_date_str.split("\n")[0].strip()
                                if "(" in pub_date_str:
                                    pub_date_str = pub_date_str.split("(")[0].strip()
                            
                            # Column 4: Deadline for making offers
                            deadline_cell = columns[3]
                            deadline_str = (await deadline_cell.inner_text()).strip()
                            
                            # Column 5: Update date
                            update_cell = columns[4]
                            update_date_str = (await update_cell.inner_text()).strip()
                            
                            # Column 6: Voivodeship (location)
                            location_cell = columns[5]
                            location = (await location_cell.inner_text()).strip()
                            
                            # Column 7: Status (active/inactive)
                            # Here we could check for an image or status text

                            # Convert the publication date to a datetime
                            publication_dt = None
                            if pub_date_str:
                                try:
                                    publication_dt = datetime.strptime(pub_date_str, "%Y-%m-%d")
                                except ValueError:
                                    logging.warning(f"Could not parse publication date from '{pub_date_str}'")
                            
                            # Convert deadline to a datetime
                            submission_dt = None
                            if deadline_str:
                                try:
                                    submission_dt = datetime.strptime(deadline_str, "%Y-%m-%d")
                                except ValueError:
                                    logging.warning(f"Could not parse deadline from '{deadline_str}'")
                            
                            # Skip if tender is older than start date
                            if start_dt and publication_dt and (publication_dt < start_dt):
                                logging.info(f"Skipping older tender '{name}' published at {publication_dt}")
                                continue
                            
                            # Fetch additional details from the detail page
                            detail_info = {}
                            if detail_url:
                                detail_info = await self.fetch_detail_info(context, detail_url)
                                
                                # Update attachment statistics
                                if detail_info.get("has_attachments") and len(detail_info.get("attachments")) > 0:
                                    attachment_stats["with_attachments"] += 1
                                elif detail_info.get("attachments_require_login"):
                                    attachment_stats["attachments_require_login"] += 1
                                else:
                                    attachment_stats["without_attachments"] += 1
                            
                            # Get organization name from detail page or default to empty string
                            org_name = detail_info.get("org_name", "")
                            
                            # Format dates for storage
                            init_date_str = ""
                            if publication_dt:
                                init_date_str = publication_dt.strftime("%Y-%m-%d")
                            
                            submission_deadline_str = ""
                            if submission_dt:
                                submission_deadline_str = submission_dt.strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Create the tender data dictionary
                            tender_data = {
                                "name": name,
                                "organization": org_name,
                                "location": location,
                                "submission_deadline": submission_deadline_str,
                                "initiation_date": init_date_str,
                                "details_url": detail_url,
                                "content_type": "tender",
                                "source_type": self.source_type,
                                # Optional: add more fields from detail_info if needed
                                "description": detail_info.get("full_description", ""),
                                "contact_info": detail_info.get("contact_info", ""),
                                "update_date": update_date_str,
                            }
                            
                            # Create Tender object
                            try:
                                tender_obj = Tender(**tender_data)
                                tenders.append(tender_obj)
                                logging.info(f"Extracted tender: {name} (org={org_name}, location={location})")
                            except Exception as err:
                                logging.error(f"Error creating Tender object: {err}")
                                continue

                        except Exception as e:
                            logging.error(f"Error parsing row on page {current_page}: {e}")
                            continue
                    
                    # Check for pagination and go to the next page if available
                    current_page += 1
                    if current_page <= max_pages:
                        # Construct the next page URL
                        next_page_url = f"{self.base_url}?page={current_page}"
                        logging.info(f"[LogintradeNetExtractor] Navigating to page {current_page}: {next_page_url}")
                        
                        # Navigate to the next page
                        await page.goto(next_page_url, wait_until='networkidle', timeout=20000)
                        await page.wait_for_selector(".defaultTable tbody tr", timeout=15000)
                    else:
                        # No more pages
                        break
                
                metadata = ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=current_page
                )
                logging.info(f"[LogintradeNetExtractor] Extraction complete. Found {len(tenders)} tenders.")
                logging.info(f"Attachment statistics:")
                logging.info(f"  - Tenders with attachments: {attachment_stats['with_attachments']}")
                logging.info(f"  - Tenders without attachments: {attachment_stats['without_attachments']}")
                logging.info(f"  - Tenders with login-required attachments: {attachment_stats['attachments_require_login']}")
                
                return {
                    # "tenders": [],
                    "tenders": tenders,
                    "metadata": metadata
                }
            
            finally:
                # Clean up browser
                await browser.close()