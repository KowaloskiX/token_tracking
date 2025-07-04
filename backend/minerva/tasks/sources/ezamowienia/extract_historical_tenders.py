import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import asyncio
import random
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from dataclasses import dataclass
from minerva.core.models.request.tender_extract import ExtractorMetadata

logging.basicConfig(level=logging.INFO)
MAX_RETRIES = 3

@dataclass
class HistoricalTenderPart:
    part_number: int
    description: str
    cpv_code: Optional[str] = None
    part_value: Optional[str] = None
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


@dataclass
class HistoricalTender:
    name: str
    organization: str
    location: str
    announcement_date: str
    details_url: str
    content_type: str = "historical_tender"
    source_type: str = "ezamowienia_historical"
    
    total_parts: int = 1
    parts_summary: Optional[str] = None
    
    main_cpv_code: Optional[str] = None
    additional_cpv_codes: Optional[List[str]] = None
    
    original_tender_url: Optional[str] = None
    
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
    
    parts: Optional[List[HistoricalTenderPart]] = None

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
                'total_parts': 1,
                'parts_summary': None,
                'original_tender_url': None,  # Add this line
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
                'realization_period': None,
                'parts': []
            }
            
            # Extract original tender announcement URL - ADD THIS SECTION
            original_url_patterns = [
                r'Adres strony internetowej prowadzonego postępowania:\s*([^\s\n]+)',
                r'Adres strony internetowej.*?postępowania:\s*([^\s\n]+)',
                r'URL.*?postępowania:\s*([^\s\n]+)',
            ]
            
            for pattern in original_url_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
                if match:
                    potential_url = match.group(1).strip()
                    # Clean up the URL (remove any trailing punctuation)
                    potential_url = re.sub(r'[.,;:]$', '', potential_url)
                    # Validate it looks like a URL
                    if potential_url.startswith(('http://', 'https://', 'www.')):
                        result['original_tender_url'] = potential_url
                        logging.info(f"Found original tender URL: {potential_url}")
                        break
            
            # Rest of your existing parsing logic...
            part_matches = re.findall(r'Część (\d+)', text_content)
            if part_matches:
                result['total_parts'] = len(set(part_matches))
                parts_info = self._parse_multi_part_tender(text_content, result['total_parts'])
                result.update(parts_info)
            else:
                single_part_info = self._parse_single_part_tender(text_content)
                result.update(single_part_info)
            
            return result

    def _parse_multi_part_tender(self, text_content: str, total_parts: int) -> Dict:
        """Parse multi-part tender and aggregate information"""
        parts = []
        parts_descriptions = []
        
        all_completion_statuses = []
        all_total_offers = []
        all_sme_offers = []
        all_lowest_prices = []
        all_highest_prices = []
        all_winning_prices = []
        all_winners = []
        all_winner_locations = []
        all_winner_sizes = []
        all_contract_dates = []
        all_contract_values = []
        all_realization_periods = []
        
        for part_num in range(1, total_parts + 1):
            part_info = self._parse_tender_part(text_content, part_num)
            if part_info:
                parts.append(part_info)
                parts_descriptions.append(f"Część {part_num}: {part_info.description}")
                
                if part_info.completion_status:
                    all_completion_statuses.append(part_info.completion_status)
                if part_info.total_offers is not None:
                    all_total_offers.append(part_info.total_offers)
                if part_info.sme_offers is not None:
                    all_sme_offers.append(part_info.sme_offers)
                if part_info.lowest_price:
                    all_lowest_prices.append(part_info.lowest_price)
                if part_info.highest_price:
                    all_highest_prices.append(part_info.highest_price)
                if part_info.winning_price:
                    all_winning_prices.append(part_info.winning_price)
                if part_info.winner_name:
                    all_winners.append(part_info.winner_name)
                if part_info.winner_location:
                    all_winner_locations.append(part_info.winner_location)
                if part_info.winner_size:
                    all_winner_sizes.append(part_info.winner_size)
                if part_info.contract_date:
                    all_contract_dates.append(part_info.contract_date)
                if part_info.contract_value:
                    all_contract_values.append(part_info.contract_value)
                if part_info.realization_period:
                    all_realization_periods.append(part_info.realization_period)
        
        parts_summary = " | ".join(parts_descriptions) if parts_descriptions else None
        
        completion_status = None
        if all_completion_statuses:
            unique_statuses = list(set(all_completion_statuses))
            if len(unique_statuses) == 1:
                completion_status = unique_statuses[0]
            else:
                completion_status = f"Mixed: {', '.join(unique_statuses)}"
        
        total_offers = sum(all_total_offers) if all_total_offers else None
        sme_offers = sum(all_sme_offers) if all_sme_offers else None

        additional_cpv_pattern = r'Dodatkowy kod CPV:\s*([^<\n]+)'
        additional_matches = re.findall(additional_cpv_pattern, text_content, re.IGNORECASE | re.DOTALL)
        additional_cpv_codes = [match.strip() for match in additional_matches] if additional_matches else None

        main_cpv_patterns = [
            r'Główny kod CPV:\s*([^<\n]+)',
            r'4\.5\.3\.\).*?Główny kod CPV:\s*([^<\n]+)',
        ]
        main_cpv_code = None
        for pattern in main_cpv_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if match:
                main_cpv_code = match.group(1).strip()
                break
        
        lowest_price = self._aggregate_price_range(all_lowest_prices, "lowest")
        highest_price = self._aggregate_price_range(all_highest_prices, "highest")
        winning_price = self._aggregate_price_range(all_winning_prices, "winning")
        
        winner_name = None
        if all_winners:
            unique_winners = list(set(all_winners))
            winner_name = ", ".join(unique_winners) if len(unique_winners) <= 3 else f"{unique_winners[0]} and {len(unique_winners)-1} others"
        
        winner_location = None
        if all_winner_locations:
            unique_locations = list(set(all_winner_locations))
            winner_location = ", ".join(unique_locations) if len(unique_locations) <= 3 else f"{unique_locations[0]} and {len(unique_locations)-1} others"
        
        winner_size = None
        if all_winner_sizes:
            unique_sizes = list(set(all_winner_sizes))
            winner_size = unique_sizes[0] if len(unique_sizes) == 1 else f"Mixed: {', '.join(unique_sizes)}"
        
        contract_date = self._aggregate_date_range(all_contract_dates)
        
        contract_value = self._aggregate_price_range(all_contract_values, "contract")
        
        realization_period = self._aggregate_periods(all_realization_periods)
        
        return {
            'main_cpv_code': main_cpv_code,
            'additional_cpv_codes': additional_cpv_codes,
            'parts_summary': parts_summary,
            'completion_status': completion_status,
            'total_offers': total_offers,
            'sme_offers': sme_offers,
            'lowest_price': lowest_price,
            'highest_price': highest_price,
            'winning_price': winning_price,
            'winner_name': winner_name,
            'winner_location': winner_location,
            'winner_size': winner_size,
            'contract_date': contract_date,
            'contract_value': contract_value,
            'realization_period': realization_period,
            'parts': parts
        }

    def _parse_tender_part(self, text_content: str, part_num: int) -> Optional[HistoricalTenderPart]:
        """Parse information for a specific tender part"""
        part_desc_pattern = f"Część {part_num}.*?4\.5\.1\.\).*?Krótki opis przedmiotu zamówienia\s*(.*?)(?=4\.5\.3\.|Część {part_num+1}|SEKCJA V)"
        desc_match = re.search(part_desc_pattern, text_content, re.IGNORECASE | re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else f"Part {part_num}"
        
        cpv_pattern = f"Część {part_num}.*?4\.5\.3\.\).*?Główny kod CPV:\s*([^<\n]+)"
        cpv_match = re.search(cpv_pattern, text_content, re.IGNORECASE | re.DOTALL)
        cpv_code = cpv_match.group(1).strip() if cpv_match else None
        
        value_pattern = f"Część {part_num}.*?4\.5\.5\.\).*?Wartość części:\s*([^<\n]+)"
        value_match = re.search(value_pattern, text_content, re.IGNORECASE | re.DOTALL)
        part_value = value_match.group(1).strip() if value_match else None
        
        completion_pattern = f"SEKCJA V ZAKOŃCZENIE POSTĘPOWANIA \(dla części {part_num}\).*?5\.1\.\).*?:\s*([^<\n]+)"
        completion_match = re.search(completion_pattern, text_content, re.IGNORECASE | re.DOTALL)
        completion_status = completion_match.group(1).strip() if completion_match else None
        
        offers_pattern = f"SEKCJA VI OFERTY \(dla części {part_num}\).*?6\.1\.\).*?:\s*(\d+)"
        offers_match = re.search(offers_pattern, text_content, re.IGNORECASE | re.DOTALL)
        total_offers = int(offers_match.group(1)) if offers_match else None
        
        sme_pattern = f"SEKCJA VI OFERTY \(dla części {part_num}\).*?6\.1\.3\.\).*?:\s*(\d+)"
        sme_match = re.search(sme_pattern, text_content, re.IGNORECASE | re.DOTALL)
        sme_offers = int(sme_match.group(1)) if sme_match else None
        
        lowest_price_pattern = f"SEKCJA VI OFERTY \(dla części {part_num}\).*?6\.2\.\).*?:\s*([^<\n]+)"
        lowest_match = re.search(lowest_price_pattern, text_content, re.IGNORECASE | re.DOTALL)
        lowest_price = lowest_match.group(1).strip() if lowest_match else None
        
        highest_price_pattern = f"SEKCJA VI OFERTY \(dla części {part_num}\).*?6\.3\.\).*?:\s*([^<\n]+)"
        highest_match = re.search(highest_price_pattern, text_content, re.IGNORECASE | re.DOTALL)
        highest_price = highest_match.group(1).strip() if highest_match else None
        
        winning_price_pattern = f"SEKCJA VI OFERTY \(dla części {part_num}\).*?6\.4\.\).*?:\s*([^<\n]+)"
        winning_match = re.search(winning_price_pattern, text_content, re.IGNORECASE | re.DOTALL)
        winning_price = winning_match.group(1).strip() if winning_match else None
        
        winner_name_pattern = f"SEKCJA VII WYKONAWCA.*?\(dla części {part_num}\).*?7\.3\.1\).*?:\s*([^<\n]+)"
        winner_name_match = re.search(winner_name_pattern, text_content, re.IGNORECASE | re.DOTALL)
        winner_name = winner_name_match.group(1).strip() if winner_name_match else None
        
        winner_size_pattern = f"SEKCJA VII WYKONAWCA.*?\(dla części {part_num}\).*?7\.2\.\).*?:\s*([^<\n]+)"
        winner_size_match = re.search(winner_size_pattern, text_content, re.IGNORECASE | re.DOTALL)
        winner_size = winner_size_match.group(1).strip() if winner_size_match else None
        
        winner_location_pattern = f"SEKCJA VII WYKONAWCA.*?\(dla części {part_num}\).*?7\.3\.4\)\s*Miejscowość:\s*([^<\n]+)"
        winner_location_match = re.search(winner_location_pattern, text_content, re.IGNORECASE | re.DOTALL)
        winner_location = winner_location_match.group(1).strip() if winner_location_match else None
        
        contract_date_pattern = f"SEKCJA VIII UMOWA \(dla części {part_num}\).*?8\.1\.\).*?:\s*([^<\n]+)"
        contract_date_match = re.search(contract_date_pattern, text_content, re.IGNORECASE | re.DOTALL)
        contract_date = contract_date_match.group(1).strip() if contract_date_match else None
        
        contract_value_pattern = f"SEKCJA VIII UMOWA \(dla części {part_num}\).*?8\.2\.\).*?:\s*([^<\n]+)"
        contract_value_match = re.search(contract_value_pattern, text_content, re.IGNORECASE | re.DOTALL)
        contract_value = contract_value_match.group(1).strip() if contract_value_match else None
        
        realization_period_pattern = f"SEKCJA VIII UMOWA \(dla części {part_num}\).*?8\.3\.\).*?:\s*([^<\n]+)"
        realization_match = re.search(realization_period_pattern, text_content, re.IGNORECASE | re.DOTALL)
        realization_period = realization_match.group(1).strip() if realization_match else None
        
        return HistoricalTenderPart(
            part_number=part_num,
            description=description,
            cpv_code=cpv_code,
            part_value=part_value,
            completion_status=completion_status,
            total_offers=total_offers,
            sme_offers=sme_offers,
            lowest_price=lowest_price,
            highest_price=highest_price,
            winning_price=winning_price,
            winner_name=winner_name,
            winner_location=winner_location,
            winner_size=winner_size,
            contract_date=contract_date,
            contract_value=contract_value,
            realization_period=realization_period
        )

    def _parse_single_part_tender(self, text_content: str) -> Dict:
        """Parse single part tender using existing logic"""
        result = {}
        
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
        cpv_patterns = [
            r'Główny kod CPV:\s*([^<\n]+)',
            r'4\.5\.3\.\).*?Główny kod CPV:\s*([^<\n]+)',
            r'CPV:\s*([0-9\-]+[^<\n]*)',
        ]
        for pattern in cpv_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if match:
                result['main_cpv_code'] = match.group(1).strip()
                break
        
        additional_cpv_pattern = r'Dodatkowy kod CPV:\s*([^<\n]+)'
        additional_matches = re.findall(additional_cpv_pattern, text_content, re.IGNORECASE | re.DOTALL)
        if additional_matches:
            result['additional_cpv_codes'] = [match.strip() for match in additional_matches]
        
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
            if match and not result.get(field_name):
                result[field_name] = match.group(1).strip()
        
        winner_patterns = [
            (r'Nazwa \(firma\) wykonawcy, któremu udzielono zamówienia.*?:\s*([^<\n]+)', 'winner_name'),
            (r'7\.3\.1\).*?:\s*([^<\n]+)', 'winner_name'),
            (r'Wielkość przedsiębiorstwa wykonawcy.*?:\s*([^<\n]+)', 'winner_size'),
            (r'7\.2\.\).*?:\s*([^<\n]+)', 'winner_size'),
        ]
        
        for pattern, field_name in winner_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if match and not result.get(field_name):
                result[field_name] = match.group(1).strip()
        
        winner_location_patterns = [
            r'7\.3\.4\)\s*Miejscowość:\s*([^<\n]+)',
            r'Miejscowość:\s*([^<\n]+)',
        ]
        for pattern in winner_location_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            if matches and not result.get('winner_location'):
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
            if match and not result.get(field_name):
                result[field_name] = match.group(1).strip()
        
        return result

    def _aggregate_price_range(self, prices: List[str], price_type: str) -> Optional[str]:
        """Aggregate price information from multiple parts"""
        if not prices:
            return None
        
        unique_prices = []
        seen = set()
        for price in prices:
            if price not in seen:
                unique_prices.append(price)
                seen.add(price)
        
        if len(unique_prices) == 1:
            return unique_prices[0]
        elif len(unique_prices) <= 3:
            return f"{price_type.title()}: {', '.join(unique_prices)}"
        else:
            return f"{price_type.title()}: {unique_prices[0]} to {unique_prices[-1]} ({len(unique_prices)} parts)"

    def _aggregate_date_range(self, dates: List[str]) -> Optional[str]:
        """Aggregate date information from multiple parts"""
        if not dates:
            return None
        
        unique_dates = list(set(dates))
        if len(unique_dates) == 1:
            return unique_dates[0]
        else:
            unique_dates.sort()
            return f"{unique_dates[0]} to {unique_dates[-1]}"

    def _aggregate_periods(self, periods: List[str]) -> Optional[str]:
        """Aggregate realization periods from multiple parts"""
        if not periods:
            return None
        
        unique_periods = list(set(periods))
        if len(unique_periods) == 1:
            return unique_periods[0]
        elif len(unique_periods) <= 3:
            return " | ".join(unique_periods)
        else:
            return f"Multiple periods ({len(unique_periods)} parts)"
    
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
    
    def _extract_original_tender_url(self, html_content: str) -> Optional[str]:
        """Extract original tender URL from the historical tender content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        patterns = [
            r'href="(https://ezamowienia\.gov\.pl/mp-client/search/list/[^"]+)"',
            r'href="(https://platformazakupowa\.pl/[^"]+)"',
            r'(https://ezamowienia\.gov\.pl/mp-client/search/list/ocds-[^"\s]+)',
            r'(https://platformazakupowa\.pl/[^"\s]+)',
        ]
        
        text_content = soup.get_text()
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content + " " + text_content, re.IGNORECASE)
            if matches:
                for match in matches:
                    if 'ocds-' in match or 'platformazakupowa' in match:
                        return match.strip()
        
        return None

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
            
            original_url = self._extract_original_tender_url(html_content)
            if original_url:
                parsed_data['original_tender_url'] = original_url
                logging.info(f"Found original tender URL: {original_url}")
            
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
        max_pages = inputs.get('max_pages', 150)
        
        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date are required")
        
        logging.info(f"Starting historical tender extraction from {start_date} to {end_date}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
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
                
                await page.wait_for_timeout(2000)
                
                notice_type_set = False
                
                try:
                    logging.info("Attempting to set notice type filter to 'TenderResultNotice' using Angular dropdown...")
                    
                    await page.wait_for_selector("app-select[formcontrolname='noticeType']", timeout=10000)
                    
                    dropdown_trigger = await page.query_selector("app-select[formcontrolname='noticeType'] .form-select")
                    if not dropdown_trigger:
                        dropdown_trigger = await page.query_selector("app-select[formcontrolname='noticeType'] select")
                    
                    if dropdown_trigger:
                        await dropdown_trigger.click()
                        await page.wait_for_timeout(500)
                        
                        tender_result_option = await page.wait_for_selector(
                            "select[formcontrolname='noticeType'] option[value='TenderResultNotice']", 
                            timeout=5000
                        )
                        if tender_result_option:
                            await tender_result_option.click()
                            await page.wait_for_timeout(500)
                            
                            notice_type_select = await page.query_selector("select[formcontrolname='noticeType']")
                            if notice_type_select:
                                selected_value = await notice_type_select.input_value()
                                if selected_value == "TenderResultNotice":
                                    logging.info("Successfully selected 'TenderResultNotice' filter using Angular dropdown")
                                    notice_type_set = True
                                else:
                                    logging.warning(f"Angular dropdown selection verification failed. Selected: {selected_value}")
                    
                except Exception as e:
                    logging.warning(f"Method 1 (Angular dropdown) for notice type selection failed: {e}")
                
                if not notice_type_set:
                    try:
                        logging.info("Trying direct select option approach...")
                        
                        notice_select_by_id = await page.query_selector("#app-select-0")
                        if notice_select_by_id:
                            await notice_select_by_id.select_option(value="TenderResultNotice")
                            
                            selected_value = await notice_select_by_id.input_value()
                            if selected_value == "TenderResultNotice":
                                logging.info("Successfully selected 'TenderResultNotice' with direct select method")
                                notice_type_set = True
                            else:
                                logging.warning(f"Direct select method verification failed. Selected: {selected_value}")
                    
                    except Exception as e:
                        logging.warning(f"Method 2 (direct select) for notice type selection failed: {e}")
                
                if not notice_type_set:
                    try:
                        logging.info("Trying JavaScript injection for notice type selection...")
                        
                        await page.evaluate("""
                            const select = document.querySelector('select[formcontrolname="noticeType"]') || 
                                        document.querySelector('#app-select-0');
                            if (select) {
                                select.value = 'TenderResultNotice';
                                select.dispatchEvent(new Event('change', { bubbles: true }));
                                select.dispatchEvent(new Event('input', { bubbles: true }));
                                select.dispatchEvent(new Event('blur', { bubbles: true }));
                            }
                        """)
                        
                        await page.wait_for_timeout(500)
                        
                        notice_type_select = await page.query_selector("select[formcontrolname='noticeType']")
                        if notice_type_select:
                            selected_value = await notice_type_select.input_value()
                            if selected_value == "TenderResultNotice":
                                logging.info("Successfully selected 'TenderResultNotice' with JavaScript injection")
                                notice_type_set = True
                            else:
                                logging.warning(f"JavaScript method verification failed. Selected: {selected_value}")
                    
                    except Exception as e:
                        logging.warning(f"Method 3 (JavaScript) for notice type selection failed: {e}")
                
                if not notice_type_set:
                    try:
                        logging.info("Trying alternative Angular dropdown approach...")
                        
                        form_select_trigger = await page.query_selector("app-select[formcontrolname='noticeType'] .form-select")
                        if form_select_trigger:
                            trigger_text = await form_select_trigger.inner_text()
                            logging.info(f"Found dropdown trigger with text: '{trigger_text}'")
                            
                            await form_select_trigger.click()
                            await page.wait_for_timeout(1000)
                            
                            tender_result_option = await page.query_selector("option:has-text('Ogłoszenie o wyniku postępowania')")
                            if tender_result_option:
                                await tender_result_option.click()
                                await page.wait_for_timeout(500)
                                
                                # Verify
                                notice_type_select = await page.query_selector("select[formcontrolname='noticeType']")
                                if notice_type_select:
                                    selected_value = await notice_type_select.input_value()
                                    if selected_value == "TenderResultNotice":
                                        logging.info("Successfully selected 'TenderResultNotice' with alternative Angular approach")
                                        notice_type_set = True
                    
                    except Exception as e:
                        logging.warning(f"Method 4 (alternative Angular) for notice type selection failed: {e}")
                
                if not notice_type_set:
                    logging.error("Failed to set notice type filter using all methods. Proceeding anyway, but results may include all notice types.")
                else:
                    logging.info("Notice type filter successfully set to 'Ogłoszenie o wyniku postępowania'")
                
                await page.wait_for_timeout(1000)
                
                start_date_set = False
                logging.info(f"Setting start date to: {start_date}")
                
                try:
                    start_date_input = await page.query_selector("lib-date[formcontrolname='publicationDateFrom'] input")
                    if start_date_input:
                        logging.info("Found start date input using lib-date selector")
                        await start_date_input.click()
                        await page.wait_for_timeout(500)
                        await start_date_input.clear()
                        await start_date_input.type(start_date, delay=100)
                        await page.keyboard.press('Tab')
                        actual_value = await start_date_input.input_value()
                        logging.info(f"Method 1: Set start date to {start_date}, actual value: {actual_value}")
                        if actual_value == start_date:
                            start_date_set = True
                except Exception as e:
                    logging.warning(f"Start date Method 1 failed: {e}")
                
                if not start_date_set:
                    try:
                        start_date_input = await page.query_selector("input[placeholder='od']")
                        if start_date_input:
                            logging.info("Found start date input using placeholder selector")
                            await start_date_input.click()
                            await page.wait_for_timeout(500)
                            await page.keyboard.press('Control+a')
                            await page.keyboard.type(start_date, delay=100)
                            await page.keyboard.press('Tab')
                            actual_value = await start_date_input.input_value()
                            logging.info(f"Method 2: Set start date to {start_date}, actual value: {actual_value}")
                            if actual_value == start_date:
                                start_date_set = True
                    except Exception as e:
                        logging.warning(f"Start date Method 2 failed: {e}")
                
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
                        start_date_input = await page.query_selector("lib-date[formcontrolname='publicationDateFrom'] input") or await page.query_selector("input[placeholder='od']")
                        if start_date_input:
                            actual_value = await start_date_input.input_value()
                            logging.info(f"Method 3: Set start date to {start_date}, actual value: {actual_value}")
                            if actual_value == start_date:
                                start_date_set = True
                    except Exception as e:
                        logging.warning(f"Start date Method 3 failed: {e}")
                
                end_date_set = False
                logging.info(f"Setting end date to: {end_date}")
                
                try:
                    end_date_input = await page.query_selector("lib-date[formcontrolname='publicationDateTo'] input")
                    if end_date_input:
                        logging.info("Found end date input using lib-date selector")
                        await end_date_input.click()
                        await page.wait_for_timeout(500)
                        await end_date_input.clear()
                        await end_date_input.type(end_date, delay=100)
                        await page.keyboard.press('Tab')
                        actual_value = await end_date_input.input_value()
                        logging.info(f"Method 1: Set end date to {end_date}, actual value: {actual_value}")
                        if actual_value == end_date:
                            end_date_set = True
                except Exception as e:
                    logging.warning(f"End date Method 1 failed: {e}")
                
                if not end_date_set:
                    try:
                        end_date_input = await page.query_selector("input[placeholder='do']")
                        if end_date_input:
                            logging.info("Found end date input using placeholder selector")
                            await end_date_input.click()
                            await page.wait_for_timeout(500)
                            await page.keyboard.press('Control+a')
                            await page.keyboard.type(end_date, delay=100)
                            await page.keyboard.press('Tab')
                            actual_value = await end_date_input.input_value()
                            logging.info(f"Method 2: Set end date to {end_date}, actual value: {actual_value}")
                            if actual_value == end_date:
                                end_date_set = True
                    except Exception as e:
                        logging.warning(f"End date Method 2 failed: {e}")
                
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
                        end_date_input = await page.query_selector("lib-date[formcontrolname='publicationDateTo'] input") or await page.query_selector("input[placeholder='do']")
                        if end_date_input:
                            actual_value = await end_date_input.input_value()
                            logging.info(f"Method 3: Set end date to {end_date}, actual value: {actual_value}")
                            if actual_value == end_date:
                                end_date_set = True
                    except Exception as e:
                        logging.warning(f"End date Method 3 failed: {e}")
                
                logging.info(f"Filter setting summary: Notice type {'✓' if notice_type_set else '✗'}, Start date {'✓' if start_date_set else '✗'}, End date {'✓' if end_date_set else '✗'}")
                
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
                                    total_parts=detail_data.get('total_parts', 1),
                                    parts_summary=detail_data.get('parts_summary'),
                                    
                                    main_cpv_code=detail_data.get('main_cpv_code'),
                                    additional_cpv_codes=detail_data.get('additional_cpv_codes'),
                                    original_tender_url=detail_data.get('original_tender_url'),
                                    
                                    completion_status=detail_data.get('completion_status'),
                                    total_offers=detail_data.get('total_offers'),
                                    sme_offers=detail_data.get('sme_offers'),
                                    lowest_price=detail_data.get('lowest_price'),
                                    highest_price=detail_data.get('highest_price'),
                                    winning_price=detail_data.get('winning_price'),
                                    winner_name=detail_data.get('winner_name'),
                                    winner_location=detail_data.get('winner_location'),
                                    winner_size=detail_data.get('winner_size'),
                                    contract_date=detail_data.get('contract_date'),
                                    contract_value=detail_data.get('contract_value'),
                                    realization_period=detail_data.get('realization_period'),
                                    full_content=detail_data.get('full_content'),
                                    parts=detail_data.get('parts', [])
                                )
                                
                                historical_tenders.append(tender)
                                url_info = f" | Original URL: {tender.original_tender_url}" if tender.original_tender_url else ""
                                logging.info(f"Extracted historical tender: {tender.name[:50]}... (Parts: {tender.total_parts}){url_info}")
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