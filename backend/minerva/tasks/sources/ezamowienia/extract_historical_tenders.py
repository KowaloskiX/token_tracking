import logging
import re
from datetime import datetime
from typing import Dict, List, Optional
import asyncio
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from dataclasses import dataclass
from minerva.core.models.request.tender_extract import ExtractorMetadata

logging.basicConfig(level=logging.INFO)
MAX_RETRIES = 3

@dataclass
class HistoricalTender:
    """Data class for historical tender information"""
    name: str
    organization: str
    location: str
    announcement_date: str
    details_url: str
    content_type: str = "historical_tender"
    source_type: str = "ezamowienia_historical"
    
    completion_status: Optional[str] = None
    total_offers: Optional[int] = None
    sme_offers: Optional[int] = None
    lowest_price: Optional[str] = None
    highest_price: Optional[str] = None
    winning_price: Optional[str] = None
    winner_name: Optional[str] = None
    winner_location: Optional[str] = None
    winner_size: Optional[str] = None
    contract_date: Optional[str] = None
    contract_value: Optional[str] = None
    realization_period: Optional[str] = None
    full_content: Optional[str] = None


class HistoricalTenderExtractor:
    def __init__(self):
        self.base_url = "https://ezamowienia.gov.pl/mo-client-board/bzp/list"
        self.source_type = "ezamowienia_historical"

    def _html_to_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator="\n")

    def _extract_value_from_text(self, text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else None

    def _parse_historical_tender_content(self, html_content: str) -> Dict:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        text_content = soup.get_text(separator="\n")
        
        result = {
            'full_content': text_content,
            'completion_status': None,
            'total_offers': None,
            'sme_offers': None,
            'lowest_price': None,
            'highest_price': None,
            'winning_price': None,
            'winner_name': None,
            'winner_location': None,
            'winner_size': None,
            'contract_date': None,
            'contract_value': None,
            'realization_period': None
        }
        
        completion_patterns = [
            r'Postępowanie zakończyło się.*?:\s*([^<\n]+)',
            r'5\.1\.\).*?:\s*([^<\n]+)',
        ]
        for pattern in completion_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if match:
                result['completion_status'] = match.group(1).strip()
                break
        
        offers_patterns = [
            r'Liczba otrzymanych ofert lub wniosków.*?:\s*(\d+)',
            r'6\.1\.\).*?:\s*(\d+)',
        ]
        for pattern in offers_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                result['total_offers'] = int(match.group(1))
                break
        
        sme_patterns = [
            r'Liczba otrzymanych od MŚP.*?:\s*(\d+)',
            r'6\.1\.3\.\).*?:\s*(\d+)',
        ]
        for pattern in sme_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                result['sme_offers'] = int(match.group(1))
                break
        
        price_patterns = [
            (r'Cena lub koszt oferty z najniższą ceną.*?:\s*([^<\n]+)', 'lowest_price'),
            (r'6\.2\.\).*?:\s*([^<\n]+)', 'lowest_price'),
            (r'Cena lub koszt oferty z najwyższą ceną.*?:\s*([^<\n]+)', 'highest_price'),
            (r'6\.3\.\).*?:\s*([^<\n]+)', 'highest_price'),
            (r'Cena lub koszt oferty wykonawcy, któremu udzielono zamówienia.*?:\s*([^<\n]+)', 'winning_price'),
            (r'6\.4\.\).*?:\s*([^<\n]+)', 'winning_price'),
        ]
        
        for pattern, field_name in price_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if match and not result[field_name]:
                result[field_name] = match.group(1).strip()
        
        winner_patterns = [
            (r'Nazwa \(firma\) wykonawcy, któremu udzielono zamówienia.*?:\s*([^<\n]+)', 'winner_name'),
            (r'7\.3\.1\).*?:\s*([^<\n]+)', 'winner_name'),
            (r'Wielkość przedsiębiorstwa wykonawcy.*?:\s*([^<\n]+)', 'winner_size'),
            (r'7\.2\.\).*?:\s*([^<\n]+)', 'winner_size'),
        ]
        
        for pattern, field_name in winner_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if match and not result[field_name]:
                result[field_name] = match.group(1).strip()
        
        winner_location_patterns = [
            r'7\.3\.4\)\s*Miejscowość:\s*([^<\n]+)',
            r'Miejscowość:\s*([^<\n]+)',
        ]
        for pattern in winner_location_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            if matches and not result['winner_location']:
                result['winner_location'] = matches[-1].strip()
                break
        
        contract_patterns = [
            (r'Data zawarcia umowy.*?:\s*([^<\n]+)', 'contract_date'),
            (r'8\.1\.\).*?:\s*([^<\n]+)', 'contract_date'),
            (r'Wartość umowy/umowy ramowej.*?:\s*([^<\n]+)', 'contract_value'),
            (r'8\.2\.\).*?:\s*([^<\n]+)', 'contract_value'),
            (r'Okres realizacji zamówienia.*?:\s*([^<\n]+)', 'realization_period'),
            (r'8\.3\.\).*?:\s*([^<\n]+)', 'realization_period'),
        ]
        
        for pattern, field_name in contract_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if match and not result[field_name]:
                result[field_name] = match.group(1).strip()
        
        for key, value in result.items():
            if isinstance(value, str) and value:
                result[key] = re.sub(r'\s+', ' ', value).strip()

        return result
    
    def _standardize_date(self, date_str: str) -> str:
        """Convert Polish date format to ISO format (YYYY-MM-DD)"""
        if not date_str:
            return date_str
            
        if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            return date_str
            
        if re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', date_str):
            parts = date_str.split('.')
            if len(parts) == 3:
                day, month, year = parts
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        polish_months = {
            'stycznia': '01', 'lutego': '02', 'marca': '03', 'kwietnia': '04',
            'maja': '05', 'czerwca': '06', 'lipca': '07', 'sierpnia': '08',
            'września': '09', 'października': '10', 'listopada': '11', 'grudnia': '12'
        }
        
        for month_name, month_num in polish_months.items():
            if month_name in date_str.lower():
                parts = date_str.split()
                if len(parts) >= 3:
                    try:
                        day = parts[0].strip()
                        year = parts[2].strip()
                        return f"{year}-{month_num}-{day.zfill(2)}"
                    except (ValueError, IndexError):
                        continue
        
        return date_str

    async def _extract_tender_details(self, context, details_url: str) -> Optional[Dict]:
        """Extract detailed information from a historical tender page"""
        page = await context.new_page()
        
        try:
            for attempt in range(MAX_RETRIES):
                try:
                    await page.goto(details_url, wait_until='domcontentloaded', timeout=30000)
                    break
                except PlaywrightTimeoutError as e:
                    logging.warning(f"Detail page navigation failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                    if attempt + 1 == MAX_RETRIES:
                        logging.error(f"Failed to navigate to {details_url} after {MAX_RETRIES} attempts")
                        return None
                    await asyncio.sleep(random.uniform(2.0, 4.0))
            
            await page.wait_for_timeout(2000)
            
            content_loaded = False
            for selector in ["mat-tab-group", ".main-content", "main", ".container"]:
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    content_loaded = True
                    break
                except PlaywrightTimeoutError:
                    continue
            
            if not content_loaded:
                logging.warning(f"Could not detect main content for {details_url}")
            
            html_content = await page.content()
            
            parsed_data = self._parse_historical_tender_content(html_content)
            
            if parsed_data.get('contract_date'):
                parsed_data['contract_date'] = self._standardize_date(parsed_data['contract_date'])
            
            return parsed_data
            
        except Exception as e:
            logging.error(f"Error extracting tender details from {details_url}: {e}")
            return None
        finally:
            await page.close()

    async def execute(self, inputs: Dict) -> Dict:
        start_date = inputs.get('start_date')
        end_date = inputs.get('end_date') 
        max_pages = inputs.get('max_pages', 10)
        
        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date are required")
        
        logging.info(f"Starting historical tender extraction from {start_date} to {end_date}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                for attempt in range(MAX_RETRIES):
                    try:
                        await page.goto(self.base_url, timeout=30000)
                        await page.wait_for_selector("form", timeout=20000)
                        break
                    except PlaywrightTimeoutError as e:
                        logging.warning(f"Initial page load failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                        if attempt + 1 == MAX_RETRIES:
                            raise e
                        await asyncio.sleep(random.uniform(2.0, 4.0))
                
                try:
                    notice_type_select = await page.query_selector("select[formcontrolname='noticeType']")
                    if notice_type_select:
                        await notice_type_select.select_option(value="TenderResultNotice")
                        logging.info("Selected 'TenderResultNotice' filter")
                except Exception as e:
                    logging.warning(f"Could not set notice type filter: {e}")
                
                # Set both start date ("od") and end date ("do") fields using multiple methods
                
                # === SET START DATE ("od") ===
                start_date_set = False
                
                # Method 1: Try lib-date with formcontrolname for start date
                try:
                    start_date_input = await page.query_selector("lib-date[formcontrolname='publicationDateFrom'] input")
                    if start_date_input:
                        logging.info("Found start date input using lib-date selector")
                        await start_date_input.click()
                        await page.wait_for_timeout(500)
                        await start_date_input.clear()
                        await start_date_input.type(start_date, delay=100)  # Type with delay
                        await page.keyboard.press('Tab')  # Tab out to trigger validation
                        actual_value = await start_date_input.input_value()
                        logging.info(f"Method 1: Set start date to {start_date}, actual value: {actual_value}")
                        if actual_value == start_date:
                            start_date_set = True
                except Exception as e:
                    logging.warning(f"Start date Method 1 failed: {e}")
                
                # Method 2: Try using placeholder selector if method 1 failed
                if not start_date_set:
                    try:
                        start_date_input = await page.query_selector("input[placeholder='od']")
                        if start_date_input:
                            logging.info("Found start date input using placeholder selector")
                            await start_date_input.click()
                            await page.wait_for_timeout(500)
                            # Select all and replace
                            await page.keyboard.press('Control+a')
                            await page.keyboard.type(start_date, delay=100)
                            await page.keyboard.press('Tab')
                            actual_value = await start_date_input.input_value()
                            logging.info(f"Method 2: Set start date to {start_date}, actual value: {actual_value}")
                            if actual_value == start_date:
                                start_date_set = True
                    except Exception as e:
                        logging.warning(f"Start date Method 2 failed: {e}")
                
                # Method 3: Try JavaScript injection as last resort for start date
                if not start_date_set:
                    try:
                        logging.info("Trying JavaScript injection method for start date")
                        await page.evaluate(f"""
                            const input = document.querySelector('lib-date[formcontrolname="publicationDateFrom"] input') ||
                                         document.querySelector('input[placeholder="od"]');
                            if (input) {{
                                input.value = '{start_date}';
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        """)
                        # Verify it was set
                        start_date_input = await page.query_selector("lib-date[formcontrolname='publicationDateFrom'] input") or await page.query_selector("input[placeholder='od']")
                        if start_date_input:
                            actual_value = await start_date_input.input_value()
                            logging.info(f"Method 3: Set start date to {start_date}, actual value: {actual_value}")
                            if actual_value == start_date:
                                start_date_set = True
                    except Exception as e:
                        logging.warning(f"Start date Method 3 failed: {e}")
                
                if start_date_set:
                    logging.info(f"Successfully set start date to {start_date}")
                else:
                    logging.error(f"Failed to set start date using all methods. Proceeding anyway...")

                # === SET END DATE ("do") ===
                end_date_set = False
                
                # Method 1: Try lib-date with formcontrolname for end date
                try:
                    end_date_input = await page.query_selector("lib-date[formcontrolname='publicationDateTo'] input")
                    if end_date_input:
                        logging.info("Found end date input using lib-date selector")
                        await end_date_input.click()
                        await page.wait_for_timeout(500)
                        await end_date_input.clear()
                        await end_date_input.type(end_date, delay=100)  # Type with delay
                        await page.keyboard.press('Tab')  # Tab out to trigger validation
                        actual_value = await end_date_input.input_value()
                        logging.info(f"Method 1: Set end date to {end_date}, actual value: {actual_value}")
                        if actual_value == end_date:
                            end_date_set = True
                except Exception as e:
                    logging.warning(f"End date Method 1 failed: {e}")
                
                # Method 2: Try using placeholder selector if method 1 failed
                if not end_date_set:
                    try:
                        end_date_input = await page.query_selector("input[placeholder='do']")
                        if end_date_input:
                            logging.info("Found end date input using placeholder selector")
                            await end_date_input.click()
                            await page.wait_for_timeout(500)
                            # Select all and replace
                            await page.keyboard.press('Control+a')
                            await page.keyboard.type(end_date, delay=100)
                            await page.keyboard.press('Tab')
                            actual_value = await end_date_input.input_value()
                            logging.info(f"Method 2: Set end date to {end_date}, actual value: {actual_value}")
                            if actual_value == end_date:
                                end_date_set = True
                    except Exception as e:
                        logging.warning(f"End date Method 2 failed: {e}")
                
                # Method 3: Try JavaScript injection as last resort for end date
                if not end_date_set:
                    try:
                        logging.info("Trying JavaScript injection method for end date")
                        await page.evaluate(f"""
                            const input = document.querySelector('lib-date[formcontrolname="publicationDateTo"] input') ||
                                         document.querySelector('input[placeholder="do"]');
                            if (input) {{
                                input.value = '{end_date}';
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        """)
                        # Verify it was set
                        end_date_input = await page.query_selector("lib-date[formcontrolname='publicationDateTo'] input") or await page.query_selector("input[placeholder='do']")
                        if end_date_input:
                            actual_value = await end_date_input.input_value()
                            logging.info(f"Method 3: Set end date to {end_date}, actual value: {actual_value}")
                            if actual_value == end_date:
                                end_date_set = True
                    except Exception as e:
                        logging.warning(f"End date Method 3 failed: {e}")
                
                if end_date_set:
                    logging.info(f"Successfully set end date to {end_date}")
                else:
                    logging.error(f"Failed to set end date using all methods. Proceeding anyway...")
                
                # Summary logging
                logging.info(f"Date setting summary: Start date {'✓' if start_date_set else '✗'}, End date {'✓' if end_date_set else '✗'}")
                
                # Wait a moment for the form to process the date changes
                await page.wait_for_timeout(1000)
                
                search_button = await page.query_selector("button:has-text('Szukaj')")
                if search_button:
                    await search_button.click()
                    await page.wait_for_timeout(3000)
                    logging.info("Clicked search button")
                else:
                    logging.error("Could not find search button")
                
                historical_tenders = []
                current_page = 1
                
                while current_page <= max_pages:
                    logging.info(f"Scraping page {current_page}...")
                    
                    try:
                        await page.wait_for_selector("table tbody tr", timeout=20000)
                    except PlaywrightTimeoutError:
                        logging.warning(f"No results found on page {current_page}")
                        break
                    
                    rows = await page.query_selector_all("table tbody tr")
                    logging.info(f"Found {len(rows)} rows on page {current_page}")
                    
                    for row in rows:
                        try:
                            cells = await row.query_selector_all("td")
                            if len(cells) < 7:
                                continue
                            
                            announcement_cell = await cells[0].inner_text()
                            if "Ogłoszenie o wyniku postępowania" not in announcement_cell:
                                continue
                            
                            tender_name = await cells[1].inner_text()  # NAZWA ZAMÓWIENIA
                            organization = await cells[2].inner_text()  # NAZWA ZAMAWIAJĄCEGO
                            city = await cells[3].inner_text()  # MIEJSCOWOŚĆ ZAMAWIAJĄCEGO
                            province = await cells[4].inner_text()  # WOJEWÓDZTWO ZAMAWIAJĄCEGO
                            date_published = await cells[5].inner_text()  # DATA PUBLIKACJI
                            
                            detail_link = await cells[-1].query_selector("a")
                            if not detail_link:
                                continue
                            
                            details_url = await detail_link.get_attribute("href")
                            if not details_url:
                                continue
                            
                            if details_url.startswith("/"):
                                details_url = f"https://ezamowienia.gov.pl{details_url}"
                            
                            location = f"{city.strip()}, {province.strip()}" if city and province else city.strip()
                            
                            standardized_date = self._standardize_date(date_published.strip())
                            
                            detail_data = await self._extract_tender_details(context, details_url)
                            
                            if detail_data:
                                tender = HistoricalTender(
                                    name=tender_name.strip(),
                                    organization=organization.strip(),
                                    location=location,
                                    announcement_date=standardized_date,
                                    details_url=details_url,
                                    **detail_data
                                )
                                
                                historical_tenders.append(tender)
                                logging.info(f"Extracted historical tender: {tender.name[:50]}...")
                            else:
                                logging.warning(f"Could not extract details for tender: {tender_name[:50]}...")
                            
                        except Exception as e:
                            logging.error(f"Error processing row: {e}")
                            continue
                    
                    next_button = await page.query_selector("a.append-arrow:has-text('Następna'):not(.disabled)")
                    if next_button and current_page < max_pages:
                        try:
                            await next_button.click()
                            await page.wait_for_timeout(3000)
                            current_page += 1
                            logging.info(f"Navigated to page {current_page}")
                        except Exception as e:
                            logging.info(f"No more pages or error navigating: {e}")
                            break
                    else:
                        logging.info("No next page button found or max pages reached")
                        break
                
                metadata = ExtractorMetadata(
                    total_tenders=len(historical_tenders),
                    pages_scraped=current_page
                )
                
                logging.info(f"Extraction complete. Found {len(historical_tenders)} historical tenders from {current_page} pages")
                
                return {
                    "tenders": historical_tenders,
                    "metadata": metadata
                }
                
            finally:
                await browser.close()