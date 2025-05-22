import logging
from datetime import datetime, timedelta
import os
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Tuple
import asyncio
import random
from uuid import uuid4
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import stealth_async  # Import the stealth helper

from minerva.core.services.vectorstore.file_content_extract.service import FileExtractionService
from minerva.core.models.request.tender_extract import ExtractorMetadata, Tender


class EGospodarkaTenderExtractor:
    def __init__(self):
        self.base_url = "https://www.przetargi.egospodarka.pl"
        self.list_url_template = f"{self.base_url}/przetargi_aktualne/sort/published_desc/offset/"

    async def goto_with_retry(
        self,
        page: Page,
        url: str,
        wait_until: str = "networkidle",
        timeout: int = 30000,
        max_retries: int = 3,
        purpose: str = "navigation"
    ):
        """Navigate to URL with retry mechanism"""
        for attempt in range(1, max_retries + 1):
            try:
                logging.debug(f"EGospodarkaTenderExtractor retrying to load URL: {url} (attempt {attempt}/{max_retries})")
                response = await page.goto(url, wait_until=wait_until, timeout=timeout)
                if response and response.status < 400:
                    return response
                else:
                    logging.warning(f"EGospodarkaTenderExtractor HTTP error or empty response on attempt {attempt} for {url}")
            except Exception as e:
                logging.warning(f"EGospodarkaTenderExtractor timeout/error during {purpose} to {url}: {str(e)} (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    retry_delay = 2 ** (attempt - 1)
                    logging.debug(f"EGospodarkaTenderExtractor waiting {retry_delay}s before retry...")
                    await asyncio.sleep(retry_delay)
        logging.error(f"EGospodarkaTenderExtractor failed {purpose} to {url} after {max_retries} attempts.")
        return None

    async def handle_cookie_consent(self, page: Page):
        """Handle cookie consent popup if present"""
        try:
            cookie_accept = await page.locator('button.fc-button.fc-cta-consent')
            await cookie_accept.click(timeout=5000)
        except Exception:
            pass

    async def handle_ads_popup(self, page: Page):
        """Handle any ad popups"""
        try:
            await page.evaluate("""
            () => {
                const modal = document.querySelector('div[style*="position: fixed"]');
                if (modal) {
                    modal.style.display = 'none';
                    document.body.style.overflow = '';
                }
            }
            """)
        except Exception as e:
            logging.debug(f"EGospodarkaTenderExtractor error handling ads popup: {str(e)}")

    async def simulate_human_behavior(self, page: Page):
        """Simulate realistic user behavior"""
        try:
            await asyncio.sleep(random.uniform(1, 2))
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await page.mouse.move(x, y, steps=random.randint(4, 8))
                await asyncio.sleep(random.uniform(0.2, 0.8))
            await page.evaluate("""
                () => {
                    return new Promise((resolve) => {
                        const maxScroll = Math.min(
                            Math.min(
                                document.body.scrollHeight,
                                document.documentElement.scrollHeight
                            ) / 2,
                            1000
                        );
                        let currentScroll = 0;
                        function smoothScroll() {
                            if (currentScroll >= maxScroll) {
                                resolve();
                                return;
                            }
                            const step = Math.floor(Math.random() * 100) + 80;
                            currentScroll = Math.min(currentScroll + step, maxScroll);
                            window.scrollTo({
                                top: currentScroll,
                                behavior: 'smooth'
                            });
                            setTimeout(smoothScroll, Math.random() * 100 + 50);
                        }
                        setTimeout(smoothScroll, 100);
                    });
                }
            """)
            await asyncio.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            logging.debug(f"EGospodarkaTenderExtractor error in simulating human behavior: {str(e)}")

    async def parse_tender_details(self, soup: BeautifulSoup, detail_url: str) -> dict:
        """Extract tender details from detail page"""
        details = {}
        auction_content = soup.find('div', id='auction_content')
        if auction_content:
            paragraphs = auction_content.find_all('p', class_='tekst')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if ':' in text:
                    key, value = text.split(':', 1)
                    key = key.replace('Nr', 'id').strip()
                    details[key.lower()] = value.strip()
            swz_link = auction_content.find('a', text=lambda t: t and 'Specyfikacja' in t)
            if swz_link:
                details['swz_url'] = swz_link.get('href')
        else:
            tender_content = soup.get_text(separator="\n", strip=True)
            details['tender_content'] = tender_content
            sections = soup.find_all(['h2', 'h3'])
            for section in sections:
                if 'SEKCJA I' in section.text:
                    org_info = section.find_next('p')
                    if org_info:
                        details['organization'] = org_info.get_text(strip=True)
                if 'SEKCJA II' in section.text:
                    name_info = section.find_next('p')
                    if name_info:
                        details['name'] = name_info.get_text(strip=True)
        return details

    async def extract_files_from_detail_page(
            self,
            context,
            details_url: str
        ) -> List[Tuple[bytes, str, Optional[str]]]:
        """Extract files from tender detail page"""
        page = await context.new_page()
        await stealth_async(page)
        processed_files = []
        # extraction_service = AssistantsFileExtractionService()
        extraction_service = FileExtractionService()
        temp_dir = None
        try:
            response = await self.goto_with_retry(
                page,
                details_url,
                wait_until="networkidle",
                timeout=30000,
                max_retries=3,
                purpose="accessing tender detail page"
            )
            if not response:
                logging.error(f"EGospodarkaTenderExtractor failed to access detail page {details_url}")
                return processed_files

            await self.handle_cookie_consent(page)
            await self.handle_ads_popup(page)
            soup = BeautifulSoup(await page.content(), 'html.parser')
            auction_content = soup.find('div', id='auction_content')
            if auction_content:
                # Remove scripts and styles
                for script in auction_content.find_all(['script', 'style']):
                    script.decompose()
                content = auction_content.get_text(separator='\n', strip=True)
                content_filename = f"tender_details_{hash(details_url)}.txt"
                content_bytes = content.encode('utf-8')
                processed_files.append((content_bytes, content_filename, details_url, content[:250], content_bytes))
                logging.info(f"EGospodarkaTenderExtractor scraped URL: {details_url}")
            else:
                logging.warning(f"EGospodarkaTenderExtractor no auction content found at {details_url}")

            unique_id = str(uuid4())
            temp_dir = Path(os.getcwd()) / "temp_downloads" / unique_id
            temp_dir.mkdir(parents=True, exist_ok=True)
            download_links = await page.query_selector_all('a[href*=".pdf"], a[href*=".doc"], a[href*=".zip"]')
            for link in download_links:
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                    async with page.expect_download(timeout=30000) as download_info:
                        download = None
                        cookie_consent_handled = False
                        for attempt in range(3):
                            try:
                                if attempt == 0:
                                    await link.click(timeout=30000)
                                else:
                                    if not cookie_consent_handled:
                                        await self.handle_cookie_consent(page)
                                        await self.handle_ads_popup(page)
                                        cookie_consent_handled = True
                                    try:
                                        await page.wait_for_selector('div.fc-dialog-overlay', state='hidden', timeout=5000)
                                    except Exception:
                                        pass
                                    await link.click(timeout=30000)
                                download = await download_info.value
                                break
                            except Exception as e:
                                if attempt == 2:
                                    raise
                                logging.warning(f"EGospodarkaTenderExtractor retrying download click (attempt {attempt+1}) for {href}: {str(e)}")
                                await asyncio.sleep(2 ** attempt)
                        if not download:
                            continue
                        file_name = download.suggested_filename
                        temp_path = Path(temp_dir) / file_name
                        await download.save_as(temp_path)
                        # Use the async wrapper
                        file_results = await extraction_service.process_file_async(temp_path)
                        for (f_content, f_name, preview, orig_bytes, orig_name) in file_results:
                            processed_files.append((f_content, f_name, href, preview, orig_bytes))
                        logging.info(f"Downloaded and processed {file_name}")
                except Exception as e:
                    logging.error(f"EGospodarkaTenderExtractor error downloading file {href}: {str(e)}")
        except Exception as e:
            logging.error(f"EGospodarkaTenderExtractor error accessing detail page {details_url}: {str(e)}")
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir)
            await page.close()
        return processed_files

    def format_date(self, date_str: str) -> str:
        """Convert Polish date to ISO format"""
        date_str = date_str.strip()
        if not date_str:
            return ""
        try:
            return datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")
        except Exception:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception as e:
                logging.error(f"EGospodarkaTenderExtractor error parsing date {date_str}: {str(e)}")
                return date_str

    async def execute(self, inputs: Dict) -> Dict:
        max_pages = 3
        start_date = inputs.get('start_date', None)
        start_dt = None
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=1)
            except ValueError:
                logging.error(f"EGospodarkaTenderExtractor invalid date format for start_date: {start_date}")

        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    slow_mo=100,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-blink-features=AutomationControlled,CollectJavascriptCoverage',
                        '--disable-features=IsolateOrigins,site-per-process,TranslateUI',
                        '--disable-site-isolation-trials',
                        '--start-maximized',
                        '--disable-remote-fonts',
                        '--disable-gpu',
                        '--no-first-run',
                        '--no-service-autorun',
                        '--password-store=basic',
                        '--use-mock-keychain',
                        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    ]
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={
                        'width': 1920 + random.randint(-100, 100),
                        'height': 1080 + random.randint(-50, 50)
                    },
                    locale='pl-PL',
                    timezone_id='Europe/Warsaw',
                )
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', { get: () => ['pl-PL', 'pl', 'en-US', 'en']});
                    window.chrome = { runtime: {} };
                """)
                page = await context.new_page()
                await stealth_async(page)
                tenders = []
                current_page = 0

                while current_page < max_pages:
                    try:
                        url = f"{self.list_url_template}{current_page}"
                        logging.debug(f"EGospodarkaTenderExtractor processing page {current_page + 1}")
                        resp = await self.goto_with_retry(
                            page, 
                            url, 
                            wait_until="networkidle", 
                            timeout=30000,
                            max_retries=3,
                            purpose=f"loading page {current_page + 1}"
                        )
                        if not resp:
                            logging.error(f"EGospodarkaTenderExtractor failed to load page {current_page + 1}")
                            raise Exception(f"Failed to load page {current_page + 1}")
                        await self.handle_cookie_consent(page)
                        await self.handle_ads_popup(page)
                        await self.simulate_human_behavior(page)
                        rows = await page.query_selector_all("table.zm tr")
                        if len(rows) <= 1:  # Only header row present
                            break
                        found_old_tender = False
                        for row in rows[1:]:
                            try:
                                cells = await row.query_selector_all("td")
                                if len(cells) < 5:
                                    continue
                                dates = await cells[0].inner_text()
                                dates = dates.split('\n')
                                pub_date = dates[0].strip() if len(dates) > 0 else ""
                                end_date = dates[1].strip() if len(dates) > 1 else ""
                                pub_dt = datetime.strptime(self.format_date(pub_date), "%Y-%m-%d")
                                if start_dt and pub_dt < start_dt:
                                    found_old_tender = True
                                    break
                                adjusted_pub_dt = pub_dt + timedelta(days=1)
                                adjusted_pub_date = adjusted_pub_dt.strftime("%Y-%m-%d")
                                location = await cells[1].inner_text()
                                category = await cells[2].inner_text()
                                organization = await cells[3].inner_text()
                                name_link = await cells[4].query_selector("a")
                                if not name_link:
                                    continue
                                name = await name_link.inner_text()
                                detail_url = await name_link.get_attribute("href")
                                if detail_url.startswith("/"):
                                    detail_url = f"{self.base_url}{detail_url}"
                                tender_data = {
                                    "name": name.strip(),
                                    "organization": organization.strip(),
                                    "location": location.strip(),
                                    "submission_deadline": self.format_date(end_date),
                                    "initiation_date": adjusted_pub_date,
                                    "details_url": detail_url,
                                    "content_type": "tender",
                                    "source_type": "egospodarka",
                                    "category": category.strip() if category else ""
                                }
                                tender = Tender(**tender_data)
                                tenders.append(tender)
                                logging.info(f"EGospodarkaTenderExtractor scraped URL: {detail_url}")
                            except Exception as e:
                                logging.error(f"EGospodarkaTenderExtractor error processing tender row: {str(e)}")
                                continue
                        if found_old_tender:
                            break
                        next_button = await page.query_selector("a:text-matches('następna|kolejna', 'i')")
                        if not next_button:
                            break
                        current_page += 1
                    except Exception as e:
                        logging.error(f"EGospodarkaTenderExtractor error processing page {current_page}: {str(e)}")
                        break
                await browser.close()
                metadata = ExtractorMetadata(
                    total_tenders=len(tenders),
                    pages_scraped=current_page + 1
                )
                logging.info(f"EGospodarkaTenderExtractor extraction complete. Found {len(tenders)} tenders.")
                return {
                    "tenders": tenders,
                    "metadata": metadata
                }
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    logging.error(f"EGospodarkaTenderExtractor error closing browser: {str(e)}")
