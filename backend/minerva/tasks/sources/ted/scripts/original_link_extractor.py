import logging
import asyncio
from datetime import datetime
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin
import re

from playwright.async_api import async_playwright

@dataclass
class TenderOriginalInfo:
    """Data class to store tender information with original source URL"""
    tender_id: str
    name: str
    organization: str
    location: str
    submission_deadline: str
    initiation_date: str
    details_url: str
    original_source_url: Optional[str]
    original_source_type: str  # e.g., "eb2b", "platformazakupowa", "TED E2NOTICE"
    found_in_section: Optional[str]  # Where the link was found

async def safe_goto(page, url, max_retries=2, initial_backoff=120, **kwargs):
    """Navigate to a URL with retry logic for 429 errors"""
    backoff = initial_backoff
    for attempt in range(max_retries + 1):
        try:
            await page.goto(url, **kwargs)
            return
        except Exception as e:
            if "429" in str(e):
                if attempt < max_retries:
                    logging.warning(f"429 error when navigating to {url}. Waiting {backoff} seconds")
                    await asyncio.sleep(backoff)
                    backoff = 300
                else:
                    logging.error(f"Failed to navigate to {url} after {max_retries + 1} attempts due to 429.")
                    raise e
            else:
                raise e

class TedOriginalLinkExtractor:
    """Extractor to find original tender page links from Polish TED tenders"""
    
    def __init__(self):
        self.logger = logging.getLogger('minerva.services.tenders.original_link_extractor')
        
        # Common patterns for original tender platforms
        self.known_platforms = {
            'eb2b.com.pl': 'eb2b',
            'platformazakupowa.pl': 'platformazakupowa',
            'ezamowienia.gov.pl': 'ezamowienia',
            'smartpzp.pl': 'smartpzp',
            'egospodarka.pl': 'egospodarka',
            'ezamawiajacy.pl': 'ezamawiajacy',
            'logintrade.pl': 'logintrade',
            'baza-konkurencyjnosci.pl': 'bazakonkurencyjnosci',
            'orlen-connect.pl': 'orlenconnect',
            'pge.pl': 'pge'
        }

    def extract_original_source_type(self, url: str) -> str:
        """Determine the source type based on URL - Enhanced for discovery"""
        if not url:
            return "TED E2NOTICE"
        
        parsed_url = urlparse(url.lower())
        domain = parsed_url.netloc
        
        # Check known platforms first
        for platform_domain, platform_type in self.known_platforms.items():
            if platform_domain in domain:
                return platform_type
        
        # For unknown platforms, provide more detailed categorization
        if domain and '.' in domain:
            # Government/Public sector
            gov_patterns = ['.gov.', '.edu.', '.org']
            if any(pattern in domain for pattern in gov_patterns):
                return f"gov_platform_{domain}"
            
            # Clear procurement indicators
            procurement_keywords = ['zamow', 'przetarg', 'tender', 'zakup', 'oglosz', 'auction', 'bid']
            if any(keyword in domain for keyword in procurement_keywords):
                return f"procurement_platform_{domain}"
            
            # Platform/service indicators
            platform_indicators = ['platform', 'portal', 'system', 'online', 'connect', 'hub']
            if any(indicator in domain for indicator in platform_indicators):
                return f"potential_platform_{domain}"
            
            # Municipality/local government patterns
            local_gov_patterns = ['miasta.', 'gmina.', 'powiat.', 'wojewodztwo.', 'urzad.']
            if any(pattern in domain for pattern in local_gov_patterns):
                return f"local_gov_{domain}"
            
            # Business domain that could be a platform
            return f"unknown_platform_{domain}"
        
        return "TED E2NOTICE"

    async def extract_original_link_from_detail_page(self, context, details_url: str) -> Tuple[Optional[str], str, Optional[str]]:
        """Extract original tender page link from TED detail page
        
        Returns:
            Tuple of (original_url, source_type, found_in_section)
        """
        page = await context.new_page()
        original_url = None
        found_in_section = None
        
        try:
            self.logger.info(f"Extracting original link from: {details_url}")
            await safe_goto(page, details_url, wait_until='networkidle', timeout=30000)
            
            # Wait for page to fully load
            await page.wait_for_timeout(2000)
            
            # Search for links in different sections
            sections_to_search = [
                {
                    'name': 'Dokumenty zamówienia',
                    'selectors': [
                        "//div[contains(@class, 'procurement-documents')]//a[contains(@href, 'http')]",
                        "//section[.//text()[contains(., 'Dokumenty zamówienia')]]//a[contains(@href, 'http')]",
                        "//div[.//span[contains(text(), 'Adres dokumentów zamówienia')]]//a[contains(@href, 'http')]",
                        "//span[contains(text(), 'Adres dokumentów zamówienia')]/following-sibling::span//a",
                        "//span[contains(@data-labels-key, 'BT-15')]//a"
                    ]
                },
                {
                    'name': 'Warunki udzielenia zamówienia',
                    'selectors': [
                        "//div[contains(@class, 'procurement-terms')]//a[contains(@href, 'http')]",
                        "//section[.//text()[contains(., 'Warunki udzielenia zamówienia')]]//a[contains(@href, 'http')]",
                        "//div[.//span[contains(text(), 'Adres na potrzeby zgłoszenia')]]//a[contains(@href, 'http')]",
                        "//span[contains(text(), 'Adres na potrzeby zgłoszenia')]/following-sibling::span//a",
                        "//span[contains(@data-labels-key, 'BT-18')]//a"
                    ]
                },
                {
                    'name': 'General links',
                    'selectors': [
                        "//a[contains(@href, 'eb2b.com.pl')]",
                        "//a[contains(@href, 'platformazakupowa.pl')]",
                        "//a[contains(@href, 'ezamowienia.gov.pl')]",
                        "//a[contains(@href, 'smartpzp.pl')]",
                        "//a[contains(@href, 'egospodarka.pl')]",
                        "//a[contains(@href, 'ezamawiajacy.pl')]",
                        "//a[contains(@href, 'logintrade.pl')]",
                        "//a[contains(@href, 'baza-konkurencyjnosci.pl')]",
                        "//a[contains(@href, 'orlen-connect.pl')]",
                        "//a[contains(@href, 'pge.pl')]"
                    ]
                }
            ]
            
            # Search through each section
            for section in sections_to_search:
                section_name = section['name']
                self.logger.debug(f"Searching in section: {section_name}")
                
                for selector in section['selectors']:
                    try:
                        links = await page.locator(f"xpath={selector}").all()
                        
                        for link in links:
                            try:
                                href = await link.get_attribute('href')
                                if href and self.is_valid_original_link(href):
                                    original_url = href
                                    found_in_section = section_name
                                    self.logger.info(f"Found original link in {section_name}: {original_url}")
                                    break
                            except Exception as e:
                                self.logger.debug(f"Error extracting href: {e}")
                                continue
                        
                        if original_url:
                            break
                    except Exception as e:
                        self.logger.debug(f"Error with selector {selector}: {e}")
                        continue
                
                if original_url:
                    break
            
            # If no specific link found, try to find any external platform link
            if not original_url:
                try:
                    all_links = await page.locator("a[href]").all()
                    for link in all_links:
                        try:
                            href = await link.get_attribute('href')
                            if href and self.is_valid_original_link(href):
                                original_url = href
                                found_in_section = "General page scan"
                                self.logger.info(f"Found link via general scan: {original_url}")
                                break
                        except Exception:
                            continue
                except Exception as e:
                    self.logger.debug(f"Error in general link scan: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error extracting original link from {details_url}: {str(e)}")
        finally:
            await page.close()
        
        source_type = self.extract_original_source_type(original_url)
        return original_url, source_type, found_in_section

    def is_valid_original_link(self, url: str) -> bool:
        """Check if URL could be an original tender platform link - INCLUSIVE for discovery"""
        if not url:
            return False
        
        # Skip TED internal links
        if 'ted.europa.eu' in url.lower():
            return False
        
        # Skip mailto and other non-http links
        if not url.lower().startswith(('http://', 'https://')):
            return False
        
        # Skip obvious non-procurement sites
        parsed_url = urlparse(url.lower())
        domain = parsed_url.netloc
        
        # Exclude common non-procurement domains
        excluded_patterns = [
            'facebook.com', 'twitter.com', 'linkedin.com', 'youtube.com',
            'google.com', 'microsoft.com', 'apple.com', 'amazon.com',
            'wikipedia.org', 'europa.eu/ted',  # But allow other europa.eu
            'mailto:', 'tel:', 'ftp:', 'file:',
            'javascript:', 'chrome-extension:',
            # Common file sharing/general sites
            'dropbox.com', 'drive.google.com', 'onedrive.com',
            'sharepoint.com', 'github.com', 'gitlab.com'
        ]
        
        for excluded in excluded_patterns:
            if excluded in url.lower():
                return False
        
        # Accept almost all other domains for discovery
        # Priority 1: Known platforms (will be categorized properly)
        for platform_domain in self.known_platforms.keys():
            if platform_domain in domain:
                return True
        
        # Priority 2: Domains with procurement-related keywords (high confidence)
        procurement_keywords = [
            'zamow', 'przetarg', 'tender', 'zakup', 'oglosz', 'auction',
            'bid', 'procurement', 'vergabe', 'ausschreibung', 'submission',
            'contract', 'rfp', 'rfq', 'eauction', 'e-auction', 'eprocurement'
        ]
        if any(keyword in domain for keyword in procurement_keywords):
            return True
        
        # Priority 3: Government and public sector domains (medium confidence)
        gov_patterns = ['.gov.', '.edu.', '.org', 'miasta.', 'gmina.', 'powiat.',
                       'wojewodztwo.', 'urzad.', 'ministerstwo.', 'agencja.',
                       'instytut.', 'centrum.', 'biuro.']
        if any(pattern in domain for pattern in gov_patterns):
            return True
        
        # Priority 4: Business domains that could be procurement platforms (lower confidence)
        # Include if domain suggests a platform/service nature
        platform_indicators = [
            'platform', 'portal', 'system', 'service', 'online', 'digital',
            'connect', 'hub', 'market', 'place', 'trade', 'business', 'pro',
            'enterprise', 'solutions', 'network'
        ]
        if any(indicator in domain for indicator in platform_indicators):
            return True
        
        # Priority 5: Accept any domain that ends with common TLDs but be more selective
        # This is for maximum discovery - we'll filter in analysis
        common_tlds = ['.pl', '.de', '.eu', '.com', '.org', '.net', '.gov', '.edu']
        if any(domain.endswith(tld) for tld in common_tlds):
            # Additional filtering: Skip if it looks like a corporate homepage
            corporate_indicators = ['www.', 'home.', 'main.', 'corporate.', 'company.']
            if not any(indicator in domain for indicator in corporate_indicators):
                return True
        
        return False

    async def extract_basic_info_from_row(self, row) -> Optional[Dict]:
        """Extract basic tender information from a table row"""
        try:
            cells = row.locator("td")
            cell_count = await cells.count()
            if cell_count < 6:
                return None
            
            # Extract tender ID and detail URL
            notice_num_cell = cells.nth(1)
            notice_link = notice_num_cell.locator("a")
            details_href = await notice_link.get_attribute("href")
            detail_url = f"https://ted.europa.eu{details_href}"
            tender_id = await notice_link.inner_text()
            
            # Extract name
            description_cell = cells.nth(2)
            name_span = description_cell.locator("span.css-u0hsu5.eeimd6y0").first
            name = await name_span.inner_text()
            if not name:
                name = await notice_link.inner_text()
            
            # Extract dates
            publication_date_str = (await cells.nth(4).inner_text()).strip()
            iso_initiation_date = ""
            try:
                day, month, year_str = publication_date_str.split("/")
                iso_initiation_date = f"{year_str}-{month}-{day}"
            except Exception:
                iso_initiation_date = publication_date_str
            
            # Extract submission deadline
            submission_deadline = ""
            if cell_count > 5:
                submission_deadline_raw = (await cells.nth(5).inner_text()).strip()
                
                if '(' in submission_deadline_raw:
                    submission_deadline_raw = submission_deadline_raw.split('(')[0].strip()
                
                try:
                    if ':00' in submission_deadline_raw and submission_deadline_raw.count(':') > 1:
                        dt = datetime.strptime(submission_deadline_raw, "%d/%m/%Y %H:%M:%S")
                    else:
                        dt = datetime.strptime(submission_deadline_raw, "%d/%m/%Y %H:%M")
                    submission_deadline = dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    submission_deadline = submission_deadline_raw
            
            # Extract location
            country = (await cells.nth(3).inner_text()).strip()
            
            return {
                'tender_id': tender_id,
                'name': name,
                'location': country,
                'submission_deadline': submission_deadline,
                'initiation_date': iso_initiation_date,
                'details_url': detail_url
            }
        except Exception as e:
            self.logger.error(f"Error extracting basic info from row: {e}")
            return None

    async def extract_organization_from_detail_page(self, context, detail_url: str) -> str:
        """Extract organization name from detail page"""
        page = await context.new_page()
        organization = ""
        try:
            await safe_goto(page, detail_url, wait_until='networkidle', timeout=20000)
            
            official_name_labels = page.locator(
                "span.label:has-text('Official name'), span.label:has-text('Oficjalna nazwa')"
            )
            if await official_name_labels.count() > 0:
                label_elem = official_name_labels.nth(0)
                parent = label_elem.locator("xpath=..")
                data_elem = parent.locator("span.data")
                if await data_elem.count() > 0:
                    organization = (await data_elem.inner_text()).strip()
        except Exception as e:
            self.logger.error(f"Error extracting organization from {detail_url}: {e}")
        finally:
            await page.close()
        
        return organization or "Unknown"

    async def execute(self, inputs: Dict) -> Dict:
        """Main execution method"""
        max_pages = inputs.get("max_pages", 5)
        start_date_str = inputs.get("start_date")
        
        # Polish TED URL
        listing_url = (
            "https://ted.europa.eu/en/search/result?"
            "search-scope=ACTIVE&scope=ACTIVE&onlyLatestVersions=false"
            "&facet.place-of-performance=SPCY%2CPOL&sortColumn=publication-date&sortOrder=DESC"
            "&page=1&simpleSearchRef=true"
        )

        async with async_playwright() as p:
            self.logger.info("Launching browser for TED original link extraction...")
            browser = await p.chromium.launch(headless=False)
            
            try:
                context = await browser.new_context()
                page = await context.new_page()

                self.logger.info(f"Navigating to {listing_url}")
                await safe_goto(page, listing_url, wait_until='networkidle', timeout=30000)

                tenders_with_original_links = []
                current_page = 1
                found_older = False
                seen_urls = set()

                while current_page <= max_pages and not found_older:
                    self.logger.info(f"Processing page {current_page}...")
                    
                    try:
                        await page.wait_for_selector("table tbody tr", timeout=10000)
                        
                        # Scroll to load all content
                        previous_count = 0
                        while True:
                            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                            await page.wait_for_timeout(2000)
                            current_count = await page.locator("table tbody tr").count()
                            if current_count == previous_count:
                                break
                            previous_count = current_count

                        rows = page.locator("table tbody tr")
                        row_count = await rows.count()
                        self.logger.info(f"Found {row_count} rows on page {current_page}")

                        for row_index in range(row_count):
                            row = rows.nth(row_index)
                            
                            # Extract basic tender info
                            basic_info = await self.extract_basic_info_from_row(row)
                            if not basic_info:
                                continue
                            
                            detail_url = basic_info['details_url']
                            if detail_url in seen_urls:
                                continue
                            seen_urls.add(detail_url)
                            
                            # Check date filtering
                            if start_date_str and basic_info['initiation_date']:
                                try:
                                    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                                    publication_dt = datetime.strptime(basic_info['initiation_date'], "%Y-%m-%d")
                                    if publication_dt < start_dt:
                                        found_older = True
                                        break
                                except ValueError:
                                    pass
                            
                            # Extract organization and original link
                            organization = await self.extract_organization_from_detail_page(context, detail_url)
                            original_url, source_type, found_in_section = await self.extract_original_link_from_detail_page(context, detail_url)
                            
                            tender_info = TenderOriginalInfo(
                                tender_id=basic_info['tender_id'],
                                name=basic_info['name'],
                                organization=organization,
                                location=basic_info['location'],
                                submission_deadline=basic_info['submission_deadline'],
                                initiation_date=basic_info['initiation_date'],
                                details_url=detail_url,
                                original_source_url=original_url,
                                original_source_type=source_type,
                                found_in_section=found_in_section
                            )
                            
                            tenders_with_original_links.append(tender_info)
                            self.logger.info(f"Processed tender {basic_info['tender_id']}: {source_type}")
                            
                            # Add delay between requests
                            await asyncio.sleep(random.uniform(1, 3))

                        if found_older:
                            break

                        # Navigate to next page
                        if current_page < max_pages:
                            next_buttons = page.locator("button[aria-label='Go to the next page']")
                            if await next_buttons.count() > 0:
                                await next_buttons.first.click()
                                await page.wait_for_timeout(3000)
                                await page.wait_for_selector("table tbody tr", timeout=15000)
                                current_page += 1
                            else:
                                break
                        else:
                            break

                    except Exception as e:
                        self.logger.error(f"Error processing page {current_page}: {e}")
                        break

                # Generate summary
                source_type_counts = {}
                for tender in tenders_with_original_links:
                    source_type = tender.original_source_type
                    source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1

                self.logger.info(f"Extraction complete. Processed {len(tenders_with_original_links)} tenders")
                self.logger.info(f"Source type distribution: {source_type_counts}")

                return {
                    'tenders': tenders_with_original_links,
                    'summary': {
                        'total_processed': len(tenders_with_original_links),
                        'pages_scraped': current_page,
                        'source_type_distribution': source_type_counts
                    }
                }

            finally:
                await context.close()
                await browser.close()

# Usage example
async def main():
    extractor = TedOriginalLinkExtractor()
    
    inputs = {
        'max_pages': 3,
        'start_date': '2025-06-01'  # Optional: filter by date
    }
    
    results = await extractor.execute(inputs)
    
    print(f"Found {len(results['tenders'])} tenders")
    print(f"Source distribution: {results['summary']['source_type_distribution']}")
    
    # Print first few results
    for i, tender in enumerate(results['tenders'][:5]):
        print(f"\n{i+1}. {tender.name}")
        print(f"   ID: {tender.tender_id}")
        print(f"   Organization: {tender.organization}")
        print(f"   Original URL: {tender.original_source_url}")
        print(f"   Source Type: {tender.original_source_type}")
        print(f"   Found in: {tender.found_in_section}")

if __name__ == "__main__":
    asyncio.run(main())