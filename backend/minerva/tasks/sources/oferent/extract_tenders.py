import json
import re
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin
from minerva.core.models.request.tender_extract import ExtractorMetadata
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class Tender(BaseModel):
    name: str = ''
    organization: str = ''
    location: str = ''
    submission_deadline: Optional[str] = ''
    initiation_date: Optional[str] = ''
    details_url: str = ''
    content_type: str = 'tender'
    source_type: str = 'oferent'

    # Oferent-specific fields
    tender_id: str = ''
    region: str = ''
    added_date: Optional[str] = ''
    client: Dict[str, Any] = Field(default_factory=dict)
    submission_info: Dict[str, Any] = Field(default_factory=dict)
    external_urls: List[str] = Field(default_factory=list)

    # Pydantic v2: enable attribute-based construction
    model_config = {'from_attributes': True}

    # If you still need a dict variant identical to the old `to_dict`
    def to_dict(self) -> Dict[str, Any]:
        # model_dump keeps aliases, handles datetimes, etc.
        return self.model_dump()

class DateStandardizer:
    @staticmethod
    def standardize_deadline(deadline_text: str) -> str:
        """Standardize deadline format"""
        if not deadline_text:
            return ""
        
        # Try to extract date in DD.MM.YYYY format
        date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', deadline_text)
        if date_match:
            day, month, year = date_match.groups()
            try:
                dt = datetime(int(year), int(month), int(day))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        return deadline_text.strip()

class OferentReportExtractor:
    def __init__(self):
        self.source_type = "oferent"
        self.base_url = "https://www.oferent.com.pl"
        
        # Known source platforms for external URL detection
        self.source_platforms = [
            "ezamowienia.gov.pl", "ted.europa.eu", "egospodarka.pl", "eb2b.com.pl", 
            "ezamawiajacy.pl", "logintrade.pl", "smartpzp.pl", "epropublico.pl", 
            "platformazakupowa.pl", "bazakonkurencyjnosci.funduszeeuropejskie.gov.pl", 
            "connect.orlen.pl", "pge.pl", "miniportal.uzp.gov.pl"
        ]

    async def _goto_with_retry(self, page, url: str, wait_until: str = 'networkidle', timeout: int = 15000):
        """Navigate to URL with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logging.info(f"Navigating to {url} (attempt {attempt + 1})")
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                logging.info(f"Successfully loaded {url}")
                return
            except Exception as e:
                logging.warning(f"Navigation attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    # Try with different wait condition
                    try:
                        await page.goto(url, wait_until='load', timeout=timeout)
                        logging.info(f"Successfully loaded {url} with 'load' condition")
                        return
                    except Exception as e2:
                        logging.warning(f"Retry with 'load' also failed: {e2}")
                        await page.wait_for_timeout(2000)  # Wait before next attempt (2 seconds)
                else:
                    raise Exception(f"Failed to navigate to {url} after {max_retries} attempts: {e}")

    def _extract_urls_from_html(self, html_content: str) -> List[str]:
        """Extract external URLs (https) from HTML content"""
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[-\w%!$&\'()*+,;=:@/~]+)*(?:\?[-\w%!$&\'()*+,;=:@/~]*)?(?:#[-\w%!$&\'()*+,;=:@/~]*)?'
        urls = re.findall(url_pattern, html_content)
        
        # Filter out URLs for images, CSS, JavaScript, etc.
        filtered_urls = []
        for url in urls:
            if ('api/placeholder' in url or 
                url.endswith('.js') or 
                url.endswith('.css') or 
                url.endswith('.jpg') or 
                url.endswith('.png') or 
                url.endswith('.svg') or
                'mailto:' in url):
                continue
                
            # Only include URLs from recognized platforms or full domain URLs
            if any(platform in url for platform in self.source_platforms) or re.match(r'https?://[-\w.]+\.[a-z]{2,}/', url):
                filtered_urls.append(url)
        
        return list(set(filtered_urls))  # Remove duplicates

    def _determine_source_type(self, urls: List[str], html_content: str) -> str:
        """Determine the source platform of the tender"""
        procurement_platforms = [
            'ezamowienia.gov.pl', 'platformazakupowa.pl', 
            'smartpzp.pl', 'e-propublico.pl', 'ted.europa.eu', 'logintrade.pl',
            'ezamawiajacy.pl', 'egospodarka.pl', 'eb2b.com.pl', 
            'bazakonkurencyjnosci.funduszeeuropejskie.gov.pl', 'connect.orlen.pl', 'pge.pl'
        ]
        
        # First check URLs as they're more reliable
        for url in urls:
            for platform in procurement_platforms:
                if platform in url:
                    return platform
        
        # Then check content
        for platform in procurement_platforms:
            if platform in html_content:
                return platform
        
        # If we find BZP mentioned, it's likely from ezamowienia.gov.pl
        if 'BZP' in html_content or 'Biuletyn Zamówień Publicznych' in html_content:
            return 'ezamowienia.gov.pl'
        
        return "oferent"

    async def _extract_tender_from_table(self, table_element, context, fetch_details=True) -> Optional[Dict]:
        """Extract tender information from a table element in the report"""
        tender_data = {
            "tender_id": "",
            "name": "",
            "organization": "",
            "location": "",
            "submission_deadline": "",
            "initiation_date": "",
            "details_url": "",
            "content_type": "tender",
            "source_type": "oferent",
            "region": "",
            "added_date": "",
            "client": {
                "name": "",
                "address": "",
                "region": "",
                "district": "",
                "phone": "",
                "email": "",
                "website": ""
            },
            "submission_info": {
                "place": "",
                "deadline": "",
                "text": ""
            },
            "external_urls": []
        }
        
        try:
            logging.info("Starting simplified table extraction...")
            
            # Method 1: Extract tender ID from header
            try:
                tender_id_span = await table_element.query_selector('th span')
                if tender_id_span:
                    tender_id = (await tender_id_span.inner_text()).strip()
                    tender_data["tender_id"] = tender_id
                    logging.info(f"Found tender ID: {tender_id}")
                else:
                    # Fallback: try to get from first th text
                    first_th = await table_element.query_selector('th')
                    if first_th:
                        th_text = await first_th.inner_text()
                        import re
                        match = re.search(r'(\d+)', th_text)
                        if match:
                            tender_id = match.group(1)
                            tender_data["tender_id"] = tender_id
                            logging.info(f"Found tender ID (fallback): {tender_id}")
            except Exception as e:
                logging.warning(f"Could not extract tender ID: {e}")
            
            # Method 2: Extract detail URL from "Przedmiot" link
            try:
                # Look for link in the "Przedmiot" row
                przedmiot_link = await table_element.query_selector('a[href*="/przetarg/"]')
                if przedmiot_link:
                    href = await przedmiot_link.get_attribute('href')
                    name = await przedmiot_link.inner_text()
                    
                    if href:
                        # Handle both relative and absolute URLs
                        if href.startswith('http'):
                            tender_data["details_url"] = href
                        else:
                            tender_data["details_url"] = f"{self.base_url}{href}"
                        tender_data["name"] = name.strip()
                        logging.info(f"Found detail URL: {tender_data['details_url']}")
                        logging.info(f"Found name: {tender_data['name']}")
                else:
                    logging.warning("No detail URL found in table")
            except Exception as e:
                logging.warning(f"Could not extract detail URL: {e}")
            
            # Method 3: Quick extraction of basic fields without iterating all rows
            try:
                # Get organization name from "Zamawiający" row
                org_rows = await table_element.query_selector_all('tr')
                for row in org_rows[:10]:  # Only check first 10 rows to avoid the 2000 row issue
                    try:
                        th = await row.query_selector('th')
                        td = await row.query_selector('td')
                        if th and td:
                            th_text = (await th.inner_text()).strip().lower()
                            if "zamawiający" in th_text:
                                org_name = (await td.inner_text()).strip()
                                tender_data["organization"] = org_name
                                tender_data["client"]["name"] = org_name
                                logging.info(f"Found organization: {org_name}")
                                break
                    except:
                        continue
            except Exception as e:
                logging.warning(f"Could not extract organization: {e}")

            # If we don't have essential data, skip this table
            if not tender_data["tender_id"] and not tender_data["details_url"]:
                logging.warning("No tender ID or detail URL found, skipping table")
                return None
            
            # If we have a detail URL, fetch ALL information from detail page
            if tender_data["details_url"]:
                logging.info(f"Fetching ALL info from detail page for {tender_data['tender_id']}")
                try:
                    await self._fetch_complete_detail_info(tender_data, context)
                except PlaywrightTimeoutError:
                    logging.warning(f"Timeout fetching details for {tender_data['tender_id']}")
                    return None  # Skip if we can't get detail info
                except Exception as detail_error:
                    logging.warning(f"Error fetching details for {tender_data['tender_id']}: {detail_error}")
                    return None
            else:
                logging.warning("No detail URL available, cannot fetch complete info")
                return None
            
            logging.info(f"Successfully extracted tender: {tender_data['tender_id']} - {tender_data['name']}")
            return tender_data
                        
        except Exception as e:
            logging.error(f"Error extracting tender from table: {e}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def _fetch_complete_detail_info(self, tender_data: Dict, context) -> None:
        """Fetch ALL information from tender detail page"""
        detail_page = None
        try:
            logging.info(f"Fetching complete detail info for tender {tender_data.get('tender_id', 'unknown')}")
            
            detail_page = await context.new_page()
            detail_page.set_default_timeout(15000)
            
            # Navigate to detail page
            await self._goto_with_retry(detail_page, tender_data["details_url"], timeout=15000)
            await detail_page.wait_for_timeout(1000)  # Wait for page to stabilize (1 second)
            
            # Extract ALL information from the detail page table
            try:
                # Look for the main tender information table
                detail_table = await detail_page.query_selector('table.przetarg')
                if detail_table:
                    logging.info("Found detail table, extracting all information...")
                    
                    # Get all rows from the detail table
                    detail_rows = await detail_table.query_selector_all('tr')
                    logging.info(f"Found {len(detail_rows)} rows in detail table")
                    
                    for i, row in enumerate(detail_rows):
                        try:
                            th = await row.query_selector('th')
                            td = await row.query_selector('td')
                            
                            if not th or not td:
                                continue
                                
                            header_text = (await th.inner_text()).strip().lower()
                            
                            if "przedmiot" in header_text:
                                tender_data["name"] = (await td.inner_text()).strip()
                                logging.debug(f"Detail: Found name: {tender_data['name']}")
                                
                            elif "zamawiający" in header_text:
                                # Handle both text and links
                                link_elem = await td.query_selector('a')
                                if link_elem:
                                    org_name = (await link_elem.inner_text()).strip()
                                else:
                                    org_name = (await td.inner_text()).strip()
                                tender_data["organization"] = org_name
                                tender_data["client"]["name"] = org_name
                                logging.debug(f"Detail: Found organization: {org_name}")
                                
                            elif "adres" in header_text:
                                address = (await td.inner_text()).strip()
                                tender_data["client"]["address"] = address
                                logging.debug(f"Detail: Found address: {address}")
                                
                            elif "województwo" in header_text:
                                region = (await td.inner_text()).strip()
                                tender_data["client"]["region"] = region
                                tender_data["region"] = region
                                logging.debug(f"Detail: Found region: {region}")
                                
                            elif "powiat" in header_text:
                                district = (await td.inner_text()).strip()
                                tender_data["client"]["district"] = district
                                logging.debug(f"Detail: Found district: {district}")
                                
                            elif "telefon" in header_text or "fax" in header_text:
                                phone = (await td.inner_text()).strip()
                                tender_data["client"]["phone"] = phone
                                logging.debug(f"Detail: Found phone: {phone}")
                                
                            elif "e-mail" in header_text:
                                link_elem = await td.query_selector('a')
                                if link_elem:
                                    href = await link_elem.get_attribute('href')
                                    if href and href.startswith('mailto:'):
                                        tender_data["client"]["email"] = href[7:]
                                    else:
                                        tender_data["client"]["email"] = (await link_elem.inner_text()).strip()
                                else:
                                    tender_data["client"]["email"] = (await td.inner_text()).strip()
                                logging.debug(f"Detail: Found email: {tender_data['client']['email']}")
                                
                            elif "www" in header_text:
                                link_elem = await td.query_selector('a')
                                if link_elem:
                                    href = await link_elem.get_attribute('href')
                                    if href:
                                        tender_data["client"]["website"] = href
                                    else:
                                        tender_data["client"]["website"] = (await link_elem.inner_text()).strip()
                                else:
                                    tender_data["client"]["website"] = (await td.inner_text()).strip()
                                logging.debug(f"Detail: Found website: {tender_data['client']['website']}")
                                
                            elif "termin składania" in header_text or "deadline" in header_text:
                                deadline = (await td.inner_text()).strip()
                                tender_data["submission_deadline"] = DateStandardizer.standardize_deadline(deadline)
                                tender_data["submission_info"]["deadline"] = deadline
                                logging.debug(f"Detail: Found deadline: {deadline}")
                                
                            elif "data" in header_text and ("dodania" in header_text or "publikacji" in header_text):
                                added_date = (await td.inner_text()).strip()
                                tender_data["added_date"] = added_date
                                tender_data["initiation_date"] = DateStandardizer.standardize_deadline(added_date)
                                logging.debug(f"Detail: Found added date: {added_date}")
                                
                        except Exception as row_error:
                            logging.debug(f"Error processing detail row {i}: {row_error}")
                            continue
                            
                else:
                    logging.warning("No detail table found on page")
                    
            except Exception as table_error:
                logging.error(f"Error processing detail table: {table_error}")
            
            # Extract content and URLs
            try:
                content_elem = await detail_page.query_selector('tr:has(th:text("Treść")) td')
                if content_elem:
                    content_html = await content_elem.inner_html()
                    content_text = await content_elem.inner_text()
                    
                    # Extract URLs from content
                    content_urls = self._extract_urls_from_html(content_html)
                    if content_urls:
                        tender_data["external_urls"] = content_urls
                        logging.debug(f"Detail: Found {len(content_urls)} external URLs")
                    
                    # Determine source type from content
                    if tender_data["source_type"] in ["oferent", "internet"]:
                        source_type = self._determine_source_type(content_urls, content_text)
                        if source_type != "oferent":
                            tender_data["source_type"] = source_type
                            logging.debug(f"Detail: Updated source type to: {source_type}")
                            
                else:
                    logging.debug("No content section found")
                    
            except Exception as content_error:
                logging.warning(f"Error extracting content: {content_error}")
            
            # Extract submission information
            try:
                submission_elem = await detail_page.query_selector('tr:has(th:text("Miejsce i termin składania")) td')
                if submission_elem:
                    submission_text = (await submission_elem.inner_text()).strip()
                    tender_data["submission_info"]["text"] = submission_text
                    
                    # Parse deadline and place
                    deadline_match = re.search(r'TERMIN SKŁADANIA[^:]*:\s*([^\n]+)', submission_text)
                    if deadline_match:
                        deadline_text = deadline_match.group(1).strip()
                        tender_data["submission_info"]["deadline"] = deadline_text
                        if not tender_data["submission_deadline"]:
                            tender_data["submission_deadline"] = DateStandardizer.standardize_deadline(deadline_text)
                        
                    place_match = re.search(r'Miejsce składania[^:]*:\s*([^\n]+)', submission_text)
                    if place_match:
                        tender_data["submission_info"]["place"] = place_match.group(1).strip()
                        
                    logging.debug("Detail: Found submission info")
                else:
                    logging.debug("No submission info found")
                    
            except Exception as submission_error:
                logging.warning(f"Error extracting submission info: {submission_error}")
            
            # Set location if not already set
            if not tender_data["location"] and tender_data["client"]["region"]:
                location_parts = []
                if tender_data["client"]["region"]:
                    location_parts.append(tender_data["client"]["region"])
                if tender_data["client"]["district"]:
                    location_parts.append(tender_data["client"]["district"])
                if tender_data["client"]["address"]:
                    location_parts.append(tender_data["client"]["address"])
                tender_data["location"] = " / ".join(location_parts)
            
            logging.info(f"Successfully processed detail page for {tender_data.get('tender_id')}")
            
        except Exception as e:
            logging.error(f"Error fetching complete detail info for tender {tender_data.get('tender_id', 'unknown')}: {e}")
            raise  # Re-raise to let caller handle
        finally:
            if detail_page:
                try:
                    await detail_page.close()
                    logging.debug(f"Closed detail page for {tender_data.get('tender_id')}")
                except Exception as e:
                    logging.warning(f"Error closing detail page: {e}")

    async def _extract_client_info(self, client_table, tender_data: Dict) -> None:
        """Extract detailed client information from the client table - DEPRECATED"""
        # This method is deprecated - all info is now extracted in _fetch_complete_detail_info
        pass

    async def execute(self, inputs: Dict) -> Dict:
        """Execute the extraction process"""
        # Get parameters from inputs
        target_date = inputs.get("target_date", None)
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        # Credentials (if provided)
        account_number = inputs.get("account_number", None)
        email = inputs.get("email", None)
        
        report_url = f"{self.base_url}/konto_raporty/{target_date}/"
        
        tenders = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']  # Better stability
            )
            try:
                context = await browser.new_context()
                
                # Set default timeouts
                context.set_default_timeout(15000)  # 15 seconds
                
                page = await context.new_page()
                
                # Login with better error handling
                try:
                    logging.info("Starting login process...")
                    await self._goto_with_retry(page, f"{self.base_url}/logowanie/")
                    
                    # Fill credentials if provided
                    if account_number:
                        try:
                            await page.wait_for_selector('#konto', timeout=5000)
                            await page.fill('#konto', account_number)
                            logging.info("Filled account number")
                        except Exception as e:
                            logging.warning(f"Could not fill account number: {e}")
                            
                    if email:
                        try:
                            await page.wait_for_selector('#email', timeout=5000)
                            await page.fill('#email', email)
                            logging.info("Filled email")
                        except Exception as e:
                            logging.warning(f"Could not fill email: {e}")
                    
                    # Click login button
                    try:
                        await page.click('button:has-text("Zaloguj")')
                        logging.info("Clicked login button")
                        await page.wait_for_url(f"{self.base_url}/**", timeout=10000)
                        logging.info("Login successful")
                    except Exception as e:
                        logging.warning(f"Login process failed: {e}")
                        # Continue anyway, might work without login
                        
                except Exception as e:
                    logging.error(f"Login failed: {e}")
                    # Continue anyway

                # Navigate to daily report
                logging.info(f"Navigating to daily report: {report_url}")
                await self._goto_with_retry(page, report_url)
                
                # Wait for any loading to complete
                await page.wait_for_timeout(2000)  # Wait for any loading to complete (2 seconds)
                
                # Find all tender tables in the report
                logging.info("Looking for tender tables...")
                # tender_tables = await page.query_selector_all('table[cellpadding="0"][cellspacing="0"]:has(th:has-text("Ogłoszenie nr"))')
                # Primary approach: Find offers_list table directly
                offers_list_table = await page.query_selector('table#offers_list')
                if offers_list_table:
                    tender_tables = await offers_list_table.query_selector_all('table[cellpadding="0"][cellspacing="0"]:has(th:has-text("Ogłoszenie nr"))')
                                
                if not tender_tables:
                    logging.warning("No tender tables found, trying alternative selector...")
                    # Try alternative selectors
                    tender_tables = await page.query_selector_all('table:has(th:has-text("Ogłoszenie nr"))')
                
                logging.info(f"Found {len(tender_tables)} tender tables in the report for {target_date}")
                
                if len(tender_tables) == 0:
                    logging.warning("No tenders found. Page content might be different than expected.")
                    # Log some page content for debugging
                    page_content = await page.content()
                    logging.debug(f"Page content preview: {page_content[:1000]}...")

                processed_tender_ids = set()  # Track unique tenders
                for i, table in enumerate(tender_tables):
                    try:
                        logging.info(f"Processing table {i+1}/{len(tender_tables)}")
                        
                        # Extract tender data from the table with timeout
                        # Note: fetch_details is now always True since we get everything from detail page
                        tender_data = await self._extract_tender_from_table(table, context, fetch_details=True)
                        
                        if not tender_data or not tender_data.get("tender_id"):
                            logging.warning(f"Skipping table {i+1} - missing required data")
                            continue


                        # For each tender:
                        tender_id = tender_data.get("tender_id")
                        if tender_id in processed_tender_ids:
                            logging.warning(f"Skipping duplicate tender: {tender_id}")
                            continue

                        processed_tender_ids.add(tender_id)  # Mark as processed
                        
                        # Create Tender object
                        try:
                            tender_obj = Tender(**tender_data)
                            tenders.append(tender_obj)
                            logging.info(f"Successfully processed tender {tender_data['tender_id']}: {tender_data['name'][:50]}...")
                        except Exception as te:
                            logging.error(f"Error creating Tender object for {tender_data.get('tender_id', 'unknown')}: {te}")
                            continue
                            
                    except PlaywrightTimeoutError:
                        logging.error(f"Timeout processing tender table {i+1}, skipping...")
                        continue
                    except Exception as e:
                        logging.error(f"Error parsing tender table {i+1}: {e}")
                        continue

                metadata = ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=1
                )
                
                logging.info(f"Extraction completed. Found {len(tenders)} tenders out of {len(tender_tables)} tables")
                
                return {
                    "tenders": tenders,
                    "metadata": metadata
                }
                
            finally:
                try:
                    await browser.close()
                    logging.info("Browser closed successfully")
                except Exception as e:
                    logging.warning(f"Error closing browser: {e}")