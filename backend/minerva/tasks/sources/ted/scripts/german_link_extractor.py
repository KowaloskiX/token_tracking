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
class GermanTenderOriginalInfo:
    """Data class to store German tender information with original source URL"""
    tender_id: str
    name: str
    organization: str
    location: str
    submission_deadline: str
    initiation_date: str
    details_url: str
    original_source_url: Optional[str]
    original_source_type: str  # e.g., "vergabe24", "subreport", "TED E2NOTICE"
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

class TedGermanOriginalLinkExtractor:
    """Extractor to find original tender page links from German TED tenders"""
    
    def __init__(self):
        self.logger = logging.getLogger('minerva.services.tenders.german_original_link_extractor')
        
        # Common patterns for German original tender platforms
        self.known_german_platforms = {
            'vergabe24.de': 'vergabe24',
            'vergabeportal.de': 'vergabeportal',
            'subreport.de': 'subreport',
            'dtad.de': 'dtad',  # Deutscher Vergabe- und Auftragsservice des Bundes
            'bund.de': 'bund_de',
            'evergabe-online.de': 'evergabe_online',
            'ausschreibung-deutschland.de': 'ausschreibung_deutschland',
            'vergabe-brandenburg.de': 'vergabe_brandenburg',
            'vergabemarktplatz.de': 'vergabemarktplatz',
            'submission.de': 'submission',
            'vergabe.bayern.de': 'vergabe_bayern',
            'vergabe.nrw.de': 'vergabe_nrw',
            'cosinex.de': 'cosinex',
            'ivepa.de': 'ivepa',
            'service.berlin.de': 'berlin_vergabe',
            'hamburg.de': 'hamburg_vergabe',
            'sachsen-anhalt.de': 'sachsen_anhalt_vergabe',
            'thueringen.de': 'thueringen_vergabe',
            'schleswig-holstein.de': 'schleswig_holstein_vergabe',
            'niedersachsen.de': 'niedersachsen_vergabe',
            'hessen.de': 'hessen_vergabe',
            'baden-wuerttemberg.de': 'baden_wuerttemberg_vergabe',
            'rheinland-pfalz.de': 'rheinland_pfalz_vergabe',
            'saarland.de': 'saarland_vergabe',
            'bremen.de': 'bremen_vergabe',
            'mecklenburg-vorpommern.de': 'mv_vergabe'
        }

    def extract_original_source_type(self, url: str) -> str:
        """Determine the source type based on URL - Enhanced for German platform discovery"""
        if not url:
            return "TED E2NOTICE"
        
        parsed_url = urlparse(url.lower())
        domain = parsed_url.netloc
        
        # Check known German platforms first
        for platform_domain, platform_type in self.known_german_platforms.items():
            if platform_domain in domain:
                return platform_type
        
        # For unknown platforms, provide detailed German-specific categorization
        if domain and '.' in domain:
            # Federal government platforms
            federal_patterns = ['.bund.de', 'bundesamt.', 'bundesministerium.', 'bundestag.', 'bundesrat.']
            if any(pattern in domain for pattern in federal_patterns):
                return f"federal_gov_{domain}"
            
            # State government platforms
            state_patterns = {
                'bayern.de': 'bayern_gov',
                'nrw.de': 'nrw_gov', 
                'berlin.de': 'berlin_gov',
                'hamburg.de': 'hamburg_gov',
                'hessen.de': 'hessen_gov',
                'sachsen.de': 'sachsen_gov',
                'baden-wuerttemberg.de': 'bw_gov',
                'thueringen.de': 'thueringen_gov',
                'sachsen-anhalt.de': 'sachsen_anhalt_gov',
                'schleswig-holstein.de': 'sh_gov',
                'niedersachsen.de': 'niedersachsen_gov',
                'rheinland-pfalz.de': 'rlp_gov',
                'saarland.de': 'saarland_gov',
                'bremen.de': 'bremen_gov',
                'mecklenburg-vorpommern.de': 'mv_gov',
                'brandenburg.de': 'brandenburg_gov'
            }
            for state_domain, state_code in state_patterns.items():
                if state_domain in domain:
                    return f"{state_code}_{domain}"
            
            # Local government platforms
            local_gov_patterns = ['stadt.', 'kommune.', 'kreis.', 'landkreis.', 'gemeinde.']
            if any(pattern in domain for pattern in local_gov_patterns):
                return f"local_gov_{domain}"
            
            # Clear German procurement indicators
            german_procurement_keywords = ['vergabe', 'ausschreibung', 'beschaffung', 'auftrag', 'tender']
            if any(keyword in domain for keyword in german_procurement_keywords):
                return f"procurement_platform_{domain}"
            
            # Platform/service indicators
            platform_indicators = ['platform', 'portal', 'system', 'online', 'connect', 'hub', 'marktplatz']
            if any(indicator in domain for indicator in platform_indicators):
                return f"potential_platform_{domain}"
            
            # General government (.de domains with gov indicators)
            gov_indicators = ['.gov.', 'amt.', 'ministerium.', 'senat.', 'regierung.']
            if any(indicator in domain for indicator in gov_indicators):
                return f"gov_platform_{domain}"
            
            # Business domain that could be a platform
            return f"unknown_platform_{domain}"
        
        return "TED E2NOTICE"

    async def extract_original_link_from_detail_page(self, context, details_url: str) -> Tuple[Optional[str], str, Optional[str]]:
        """Extract original tender page link from German TED detail page
        
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
            
            # Search for links in different sections (German and English)
            sections_to_search = [
                {
                    'name': 'Vergabeunterlagen / Tender Documents',
                    'selectors': [
                        "//div[contains(@class, 'procurement-documents')]//a[contains(@href, 'http')]",
                        "//section[.//text()[contains(., 'Dokumenty zamówienia') or contains(., 'Tender Documents') or contains(., 'Vergabeunterlagen')]]//a[contains(@href, 'http')]",
                        "//div[.//span[contains(text(), 'Adres dokumentów zamówienia') or contains(text(), 'Address of procurement documents') or contains(text(), 'Adresse der Vergabeunterlagen')]]//a[contains(@href, 'http')]",
                        "//span[contains(text(), 'Adres dokumentów zamówienia') or contains(text(), 'Address of procurement documents')]/following-sibling::span//a",
                        "//span[contains(@data-labels-key, 'BT-15')]//a"
                    ]
                },
                {
                    'name': 'Vergabebedingungen / Tender Conditions',
                    'selectors': [
                        "//div[contains(@class, 'procurement-terms')]//a[contains(@href, 'http')]",
                        "//section[.//text()[contains(., 'Warunki udzielenia zamówienia') or contains(., 'Tender conditions') or contains(., 'Vergabebedingungen')]]//a[contains(@href, 'http')]",
                        "//div[.//span[contains(text(), 'Adres na potrzeby zgłoszenia') or contains(text(), 'Address for submission') or contains(text(), 'Adresse für die Einreichung')]]//a[contains(@href, 'http')]",
                        "//span[contains(text(), 'Adres na potrzeby zgłoszenia') or contains(text(), 'Address for submission')]/following-sibling::span//a",
                        "//span[contains(@data-labels-key, 'BT-18')]//a"
                    ]
                },
                {
                    'name': 'Weitere Informationen / Further Information',
                    'selectors': [
                        "//div[contains(@class, 'further-info')]//a[contains(@href, 'http')]",
                        "//section[.//text()[contains(., 'Weitere Informationen') or contains(., 'Further information')]]//a[contains(@href, 'http')]",
                        "//div[.//span[contains(text(), 'Profil nabywcy') or contains(text(), 'Buyer profile') or contains(text(), 'Käuferprofil')]]//a[contains(@href, 'http')]",
                        "//span[contains(@data-labels-key, 'BT-508')]//a",
                        "//span[contains(@data-labels-key, 'BT-509')]//a"
                    ]
                },
                {
                    'name': 'German Platform Links',
                    'selectors': [
                        "//a[contains(@href, 'vergabe24.de')]",
                        "//a[contains(@href, 'vergabeportal.de')]",
                        "//a[contains(@href, 'subreport.de')]",
                        "//a[contains(@href, 'dtad.de')]",
                        "//a[contains(@href, 'bund.de')]",
                        "//a[contains(@href, 'evergabe-online.de')]",
                        "//a[contains(@href, 'ausschreibung-deutschland.de')]",
                        "//a[contains(@href, 'vergabe-brandenburg.de')]",
                        "//a[contains(@href, 'vergabemarktplatz.de')]",
                        "//a[contains(@href, 'submission.de')]",
                        "//a[contains(@href, 'vergabe.bayern.de')]",
                        "//a[contains(@href, 'vergabe.nrw.de')]",
                        "//a[contains(@href, 'cosinex.de')]",
                        "//a[contains(@href, 'ivepa.de')]",
                        "//a[contains(@href, '.de/vergabe')]",
                        "//a[contains(@href, '/ausschreibung')]"
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
                                if href and self.is_valid_german_original_link(href):
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
            
            # If no specific link found, try to find any external German platform link
            if not original_url:
                try:
                    all_links = await page.locator("a[href]").all()
                    for link in all_links:
                        try:
                            href = await link.get_attribute('href')
                            if href and self.is_valid_german_original_link(href):
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

    def select_most_specific_url(self, urls: list[str]) -> str:
        """Select the most specific URL from a list, preferring paths over domain-only URLs"""
        if not urls:
            return None
        
        # Sort URLs by specificity (longer paths, https over http, specific endpoints)
        def url_specificity_score(url: str) -> int:
            score = 0
            
            # Prefer https over http
            if url.startswith('https://'):
                score += 10
            
            # Count path segments (more specific)
            path_segments = url.split('/')[3:]  # Skip protocol and domain
            score += len([seg for seg in path_segments if seg])  # Count non-empty segments
            
            # Prefer URLs with specific endpoints
            if '/documents' in url:
                score += 5
            if '/notice/' in url:
                score += 3
            if '/Satellite/' in url:
                score += 2
                
            # Penalize domain-only URLs
            if url.count('/') <= 2:  # Just protocol and domain
                score -= 10
                
            return score
        
        # Sort by specificity score (highest first)
        sorted_urls = sorted(urls, key=url_specificity_score, reverse=True)
        return sorted_urls[0]

    def is_support_link(self, url: str) -> bool:
        """Check if URL is a support/help link that should not be considered as main platform"""
        if not url:
            return False
            
        url_lower = url.lower()
        support_indicators = [
            'support.', '/support/', 'help.', '/help/', 'faq', 'hilfe',
            'anleitung', 'tutorial', 'guide', 'documentation', '/docs/',
            'manual', 'handbuch', 'info@', 'contact', 'kontakt'
        ]
        
        return any(indicator in url_lower for indicator in support_indicators)

    def is_valid_german_original_link(self, url: str) -> bool:
        """Check if URL could be an original German tender platform link - INCLUSIVE for discovery"""
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
        # Priority 1: Known German platforms (will be categorized properly)
        for platform_domain in self.known_german_platforms.keys():
            if platform_domain in domain:
                return True
        
        # Priority 2: Domains with procurement-related keywords (high confidence)
        german_procurement_keywords = [
            'vergabe', 'ausschreibung', 'tender', 'procurement', 'submission',
            'beschaffung', 'auftrag', 'bieter', 'angebot', 'konzession',
            'wettbewerb', 'konkurrenz', 'einkauf', 'ankauf'
        ]
        if any(keyword in domain for keyword in german_procurement_keywords):
            return True
        
        # Priority 3: German government and public sector domains (medium confidence)
        german_gov_patterns = [
            '.de', '.gov.de', '.bund.de', '.bayern.de', '.nrw.de', '.berlin.de',
            '.hamburg.de', '.hessen.de', '.sachsen.de', '.baden-wuerttemberg.de',
            '.thueringen.de', '.sachsen-anhalt.de', '.schleswig-holstein.de',
            '.niedersachsen.de', '.rheinland-pfalz.de', '.saarland.de',
            '.bremen.de', '.mecklenburg-vorpommern.de', '.brandenburg.de',
            'stadt.', 'kommune.', 'kreis.', 'landkreis.', 'gemeinde.',
            'bundesamt.', 'landesamt.', 'ministerium.', 'senat.', 'regierung.'
        ]
        if any(pattern in domain for pattern in german_gov_patterns):
            return True
        
        # Priority 4: Business domains that could be procurement platforms (lower confidence)
        platform_indicators = [
            'platform', 'portal', 'system', 'service', 'online', 'digital',
            'connect', 'hub', 'market', 'place', 'trade', 'business', 'pro',
            'enterprise', 'solutions', 'network', 'marktplatz', 'dienst'
        ]
        if any(indicator in domain for indicator in platform_indicators):
            return True
        
        # Priority 5: European domains for broader discovery
        eu_tlds = ['.de', '.eu', '.at', '.ch', '.com', '.org', '.net', '.gov']
        if any(domain.endswith(tld) for tld in eu_tlds):
            # Additional filtering: Skip if it looks like a corporate homepage
            corporate_indicators = ['www.', 'home.', 'main.', 'corporate.', 'company.', 'unternehmen.']
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
            
            # Try different language versions for organization name
            official_name_labels = page.locator(
                "span.label:has-text('Official name'), span.label:has-text('Oficjalna nazwa'), span.label:has-text('Offizielle Bezeichnung')"
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
        
        # German TED URL
        listing_url = (
            "https://ted.europa.eu/en/search/result?"
            "search-scope=ACTIVE&scope=ACTIVE&onlyLatestVersions=false"
            "&facet.place-of-performance=SPCY%2CDEU&sortColumn=publication-date&sortOrder=DESC"
            "&page=1&simpleSearchRef=true"
        )

        async with async_playwright() as p:
            self.logger.info("Launching browser for German TED original link extraction...")
            browser = await p.chromium.launch(headless=False)
            
            try:
                context = await browser.new_context()
                page = await context.new_page()

                self.logger.info(f"Navigating to {listing_url}")
                await safe_goto(page, listing_url, wait_until='networkidle', timeout=30000)

                german_tenders_with_original_links = []
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
                            
                            tender_info = GermanTenderOriginalInfo(
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
                            
                            german_tenders_with_original_links.append(tender_info)
                            self.logger.info(f"Processed German tender {basic_info['tender_id']}: {source_type}")
                            
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

                # Generate enhanced summary for German platform discovery
                source_type_counts = {}
                discovered_domains = {}
                confidence_levels = {
                    'known_platforms': [],
                    'procurement_platforms': [],
                    'potential_platforms': [],
                    'federal_gov': [],
                    'state_gov': [],
                    'local_gov': [],
                    'gov_platforms': [],
                    'unknown_platforms': [],
                    'ted_only': []
                }
                
                for tender in german_tenders_with_original_links:
                    source_type = tender.original_source_type
                    source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
                    
                    # Categorize for discovery analytics
                    if source_type == "TED E2NOTICE":
                        confidence_levels['ted_only'].append(tender)
                    elif source_type in self.known_german_platforms.values():
                        confidence_levels['known_platforms'].append(tender)
                    elif source_type.startswith('procurement_platform_'):
                        domain = source_type.replace('procurement_platform_', '')
                        confidence_levels['procurement_platforms'].append(tender)
                        discovered_domains[domain] = discovered_domains.get(domain, 0) + 1
                    elif source_type.startswith('potential_platform_'):
                        domain = source_type.replace('potential_platform_', '')
                        confidence_levels['potential_platforms'].append(tender)
                        discovered_domains[domain] = discovered_domains.get(domain, 0) + 1
                    elif source_type.startswith('federal_gov_'):
                        domain = source_type.replace('federal_gov_', '')
                        confidence_levels['federal_gov'].append(tender)
                        discovered_domains[domain] = discovered_domains.get(domain, 0) + 1
                    elif any(state in source_type for state in ['bayern_gov', 'nrw_gov', 'berlin_gov', 'hamburg_gov']):
                        confidence_levels['state_gov'].append(tender)
                        domain = source_type.split('_', 2)[-1] if '_' in source_type else source_type
                        discovered_domains[domain] = discovered_domains.get(domain, 0) + 1
                    elif source_type.startswith('local_gov_'):
                        domain = source_type.replace('local_gov_', '')
                        confidence_levels['local_gov'].append(tender)
                        discovered_domains[domain] = discovered_domains.get(domain, 0) + 1
                    elif source_type.startswith('gov_platform_'):
                        domain = source_type.replace('gov_platform_', '')
                        confidence_levels['gov_platforms'].append(tender)
                        discovered_domains[domain] = discovered_domains.get(domain, 0) + 1
                    elif source_type.startswith('unknown_platform_'):
                        domain = source_type.replace('unknown_platform_', '')
                        confidence_levels['unknown_platforms'].append(tender)
                        discovered_domains[domain] = discovered_domains.get(domain, 0) + 1

                self.logger.info(f"German TED extraction complete. Processed {len(german_tenders_with_original_links)} tenders")
                self.logger.info(f"Discovered {len(discovered_domains)} unique German domains")
                self.logger.info(f"German discovery breakdown:")
                for category, items in confidence_levels.items():
                    if items:
                        self.logger.info(f"  {category}: {len(items)} tenders")

                return {
                    'tenders': german_tenders_with_original_links,
                    'summary': {
                        'total_processed': len(german_tenders_with_original_links),
                        'pages_scraped': current_page,
                        'source_type_distribution': source_type_counts
                    },
                    'discovery_analytics': {
                        'total_unique_domains': len(discovered_domains),
                        'discovered_domains': discovered_domains,
                        'confidence_breakdown': {k: len(v) for k, v in confidence_levels.items()},
                        'newly_discovered_platforms': [
                            domain for domain in discovered_domains.keys() 
                            if not any(known in domain for known in self.known_german_platforms.keys())
                        ],
                        'german_specific_insights': {
                            'federal_platforms': len(confidence_levels['federal_gov']),
                            'state_platforms': len(confidence_levels['state_gov']),
                            'local_platforms': len(confidence_levels['local_gov']),
                            'procurement_specific': len(confidence_levels['procurement_platforms'])
                        }
                    }
                }

            finally:
                await context.close()
                await browser.close()

# Usage example
async def main():
    extractor = TedGermanOriginalLinkExtractor()
    
    inputs = {
        'max_pages': 3,
        'start_date': '2025-06-01'  # Optional: filter by date
    }
    
    results = await extractor.execute(inputs)
    
    print(f"Found {len(results['tenders'])} German tenders")
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