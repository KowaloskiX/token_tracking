import asyncio
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from playwright.async_api import async_playwright, Browser, BrowserContext, TimeoutError
from typing import Dict, Any, List, Set, Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, AnyUrl, validator
import time
from collections import deque
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# URL processing
def ensure_url_scheme(url: str) -> str:
    """Ensure URL has a scheme, defaulting to https."""
    parsed = urlparse(url)
    if not parsed.scheme:
        return urlunparse(parsed._replace(scheme="https"))
    return url

# LRU Cache implementation
class LRUCache:
    def __init__(self, capacity: int):
        self.cache = {}
        self.queue = deque(maxlen=capacity)
        self.capacity = capacity

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        if key in self.cache:
            value = self.cache[key]
            if time.time() - value['timestamp'] < CACHE_EXPIRATION:
                self.queue.remove(key)
                self.queue.append(key)
                return value
            else:
                del self.cache[key]
        return None

    def put(self, key: str, value: Dict[str, Any]):
        if key in self.cache:
            self.queue.remove(key)
        elif len(self.cache) >= self.capacity:
            oldest = self.queue.popleft()
            del self.cache[oldest]
        self.cache[key] = value
        self.queue.append(key)

# Constants
CACHE_EXPIRATION = 3600  # 1 hour
cache = LRUCache(1000)

# Browser pool
class BrowserPool:
    def __init__(self, max_browsers: int = 3):
        self.max_browsers = max_browsers
        self.browsers: List[Browser] = []
        self.contexts: List[BrowserContext] = []
        self.lock = asyncio.Lock()
        self.initialized = False
        self.playwright = None

    async def initialize(self):
        if self.initialized:
            return
        async with self.lock:
            if not self.initialized:
                self.playwright = await async_playwright().start()
                for _ in range(self.max_browsers):
                    browser = await self.playwright.chromium.launch(
                        args=['--no-sandbox', '--disable-dev-shm-usage']
                    )
                    context = await browser.new_context(
                        viewport={'width': 1280, 'height': 720},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    )
                    self.browsers.append(browser)
                    self.contexts.append(context)
                self.initialized = True

    async def get_context(self) -> BrowserContext:
        if not self.initialized:
            await self.initialize()
        async with self.lock:
            context = self.contexts[0]
            self.contexts.append(self.contexts.pop(0))
            return context

    async def cleanup(self):
        async with self.lock:
            for context in self.contexts:
                await context.close()
            for browser in self.browsers:
                await browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.initialized = False

browser_pool = BrowserPool()

# Models
class UrlInput(BaseModel):
    urls: List[AnyUrl]
    timeout: int = 30000  # 30 seconds default timeout

    @validator('urls')
    def ensure_https(cls, urls):
        return [ensure_url_scheme(str(url)) for url in urls]

# Content extraction functions
def extract_title(soup: BeautifulSoup) -> str:
    """Extract page title with fallbacks."""
    try:
        # Try meta title first
        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            return meta_title['content'].strip()

        # Try title tag
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        # Fall back to h1
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text(strip=True)

        return ""
    except Exception as e:
        logger.error(f"Error extracting title: {str(e)}")
        return ""

def extract_favicon(soup: BeautifulSoup, base_url: str) -> str:
    """Extract favicon URL with multiple fallback options."""
    try:
        # Try common favicon locations
        for rel in ['icon', 'shortcut icon', 'apple-touch-icon']:
            favicon = soup.find('link', rel=lambda r: r and rel in r.lower())
            if favicon and favicon.get('href'):
                return urljoin(base_url, favicon['href'])

        # Check for favicon.ico
        return urljoin(base_url, '/favicon.ico')
    except Exception as e:
        logger.error(f"Error extracting favicon: {str(e)}")
        return ""

def is_valid_internal_link(href: str, base_domain: str) -> bool:
    """Validate if a link is internal and worth crawling."""
    try:
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'data:')):
            return False

        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != base_domain:
            return False

        # Avoid media files and other non-html content
        if any(href.lower().endswith(ext) for ext in [
            '.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', 
            '.xls', '.xlsx', '.zip', '.tar', '.gz'
        ]):
            return False

        return True
    except:
        return False

def extract_important_links(soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    """Extract and validate important links from the page."""
    try:
        base_domain = urlparse(base_url).netloc
        important_links = []
        seen_urls = set()

        # Priority areas for link extraction
        priority_containers = soup.select('main, article, [role="main"], nav, #content, .content')
        if not priority_containers:
            priority_containers = [soup]

        for container in priority_containers:
            for link in container.find_all('a', href=True):
                href = link['href']
                if not is_valid_internal_link(href, base_domain):
                    continue

                full_url = urljoin(base_url, href)
                if full_url in seen_urls:
                    continue

                seen_urls.add(full_url)
                link_text = link.get_text(strip=True)

                if link_text and len(link_text) > 1:
                    important_links.append({
                        "url": full_url,
                        "text": link_text
                    })

        return important_links
    except Exception as e:
        logger.error(f"Error extracting links: {str(e)}")
        return []

router = APIRouter()

# In-memory cache
cache: Dict[str, Dict[str, Any]] = {}
CACHE_EXPIRATION = 3600  # Cache expiration time in seconds (1 hour)

# Browser instance management
browser: Optional[Browser] = None
context: Optional[BrowserContext] = None

def ensure_url_scheme(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        return urlunparse(parsed._replace(scheme="https"))
    return url

class UrlInput(BaseModel):
    url: AnyUrl
    timeout: int = 5000

    @validator('url', pre=True)
    def ensure_https(cls, v):
        return ensure_url_scheme(v)

class UrlInputs(BaseModel):
    urls: List[AnyUrl]
    timeout: int = 5000
    wait_for_dynamic: bool = True  # Allow control over waiting for dynamic content

    @validator('urls', pre=True, each_item=True)
    def ensure_https(cls, v):
        return ensure_url_scheme(v)

# Semaphore to limit concurrent scrapes
sem = asyncio.Semaphore(10)

# Set to keep track of scraped URLs
scraped_urls: Set[str] = set()

async def initialize_browser():
    """Initialize browser instance if not already running."""
    global browser, context
    if not browser:
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            args=['--no-sandbox', '--disable-dev-shm-usage'],
            handle_sigint=True,
            handle_sigterm=True,
            handle_sighup=True,
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )

async def cleanup_browser():
    """Clean up browser resources."""
    global browser, context
    if context:
        await context.close()
    if browser:
        await browser.close()
    browser = None
    context = None

def clean_text(text: str) -> str:
    """
    Clean extracted text by removing unwanted elements and normalizing spacing.
    """
    # Remove common unwanted patterns
    patterns_to_remove = [
        r'\{[^}]*\}',  # Remove content in curly braces
        r'\[[^\]]*\]',  # Remove content in square brackets
        r'<[^>]*>',    # Remove any remaining HTML tags
        r'(?i)javascript:|mailto:|tel:',  # Remove common prefixes
        r'[\r\n\t]+',  # Replace multiple newlines/tabs with single space
        r'\s{2,}',     # Replace multiple spaces with single space
    ]
    
    cleaned = text
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, ' ', cleaned)
    
    # Split into lines, clean each line
    lines = cleaned.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        # Skip empty or very short lines
        if len(line) < 2:
            continue
        # Skip lines that are likely navigation/menu items
        if len(line) < 20 and any(char in line for char in ['→', '|', '/']):
            continue
        # Skip lines that are likely URLs or file paths
        if re.match(r'^https?://|^/|^\./', line):
            continue
        cleaned_lines.append(line)
    
    # Join lines with proper spacing
    return '\n\n'.join(cleaned_lines)

def should_skip_element(element) -> bool:
    """
    Check if an element should be skipped during text extraction.
    """
    skip_tags = {
        'script', 'style', 'noscript', 'iframe', 'svg', 'img', 'button',
        'input', 'select', 'textarea', 'form', 'nav', 'header', 'footer',
        'aside', 'menu', 'dialog'
    }
    
    skip_classes = {
        'nav', 'navigation', 'menu', 'sidebar', 'footer', 'header',
        'cookie', 'popup', 'modal', 'advertisement', 'ad-', 'social',
        'sharing', 'share-', 'widget', 'tracking', 'analytics', 'breadcrumb'
    }
    
    skip_ids = {
        'nav', 'navigation', 'menu', 'sidebar', 'footer', 'header',
        'cookie', 'popup', 'modal', 'ad-', 'social', 'sharing',
        'share-', 'widget'
    }
    
    # Check tag name
    if element.name in skip_tags:
        return True
    
    # Check classes
    element_classes = element.get('class', [])
    if isinstance(element_classes, str):
        element_classes = [element_classes]
    for class_ in element_classes:
        if any(skip in class_.lower() for skip in skip_classes):
            return True
    
    # Check id
    element_id = element.get('id', '')
    if any(skip in element_id.lower() for skip in skip_ids):
        return True
    
    return False

async def extract_page_text(page) -> str:
    """
    Extract text without duplicates by being more selective about which elements to extract from.
    """
    try:
        # Remove only essential elements that never contain useful content
        await page.evaluate("""() => {
            const elementsToRemove = document.querySelectorAll('script, style');
            elementsToRemove.forEach(el => el.remove());
        }""")
        
        # Extract text with a more precise approach
        text_content = await page.evaluate("""() => {
            // Helper function to get direct text content of an element (excluding children)
            function getDirectTextContent(element) {
                let text = '';
                for (const node of element.childNodes) {
                    if (node.nodeType === 3) { // Text node
                        text += node.textContent;
                    }
                }
                return text.trim();
            }
            
            // Get all text content while avoiding duplicates
            function getAllText() {
                const textPieces = new Set();
                
                // Function to process an element
                function processElement(element) {
                    // Get direct text from this element
                    const directText = getDirectTextContent(element);
                    if (directText) {
                        textPieces.add(directText);
                    }
                    
                    // Process children if this is not a text-specific element
                    if (!['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'].includes(element.tagName.toLowerCase())) {
                        for (const child of element.children) {
                            processElement(child);
                        }
                    }
                }
                
                // Get text from specific text-containing elements first
                const textElements = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li');
                textElements.forEach(el => {
                    const text = el.textContent.trim();
                    if (text) textPieces.add(text);
                });
                
                // If no text found, try processing the main content areas
                if (textPieces.size === 0) {
                    const mainElements = document.querySelectorAll('main, article, [role="main"], .content, #content');
                    mainElements.forEach(processElement);
                }
                
                // If still no text, process the body
                if (textPieces.size === 0) {
                    processElement(document.body);
                }
                
                return Array.from(textPieces).join('\\n');
            }
            
            return getAllText();
        }""")
        
        if text_content:
            # Simple cleaning to normalize whitespace and remove empty lines
            cleaned = re.sub(r'\s+', ' ', text_content)
            lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
            return '\n'.join(lines)
            
        return ""
        
    except Exception as e:
        logger.error(f"Error in text extraction: {str(e)}")
        return ""

def clean_text(text: str) -> str:
    """
    Minimal text cleaning that preserves most content.
    Only removes excessive whitespace and normalizes line endings.
    """
    if not text:
        return ""
    
    # Replace multiple spaces with single space
    cleaned = re.sub(r'\s+', ' ', text)
    
    # Split into lines
    lines = cleaned.split('\n')
    
    # Remove empty lines and trim each line
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    
    # Join with newlines
    return '\n'.join(cleaned_lines)

async def get_page_content(url: str, wait_for_dynamic: bool = True):
    """Get page content with minimal filtering."""
    global context
    
    if url in cache:
        cached_data = cache[url]
        if time.time() - cached_data['timestamp'] < CACHE_EXPIRATION:
            return cached_data['content'], cached_data['text']
    
    async with sem:
        try:
            page = await context.new_page()
            
            # Don't block any resources
            page.set_default_timeout(45000)
            page.set_default_navigation_timeout(45000)
            
            # Simple navigation with one retry
            try:
                response = await page.goto(url, wait_until="domcontentloaded")
                if not response or not response.ok:
                    await asyncio.sleep(2)
                    response = await page.goto(url, wait_until="domcontentloaded")
            except Exception as e:
                logger.error(f"Navigation error for {url}: {str(e)}")
                await page.close()
                return None, None
            
            if not response or not response.ok:
                await page.close()
                return None, None
            
            if wait_for_dynamic:
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass  # Continue even if timeout occurs
                
                # Simple scroll to trigger lazy loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
            
            content = await page.content()
            text = await extract_page_text(page)
            
            if content and text:
                cache[url] = {
                    'content': content,
                    'text': text,
                    'timestamp': time.time()
                }
            
            await page.close()
            return content, text
            
        except Exception as e:
            logger.error(f"Error while getting page content for {url}: {str(e)}")
            if 'page' in locals():
                await page.close()
            return None, None
        

@router.post("/scrape-site")
async def scrape(input: UrlInputs):
    try:
        await initialize_browser()
        base_urls = input.urls
        results = []
        
        for url in base_urls:
            url_str = str(url)
            if url_str in scraped_urls:
                continue
                
            scraped_urls.add(url_str)
            
            try:
                page_content, page_text = await get_page_content(url_str, input.wait_for_dynamic)
                if not page_content:
                    continue
                
                soup = BeautifulSoup(page_content, "html.parser")
                result = {
                    "url": url_str,
                    "title": extract_title(soup),
                    "favicon": extract_favicon(soup, url_str),
                    "links": extract_important_links(soup, url_str),
                    "text": page_text
                }
                
                results.append(result)
                
            except Exception as e:
                print(f"Error processing {url_str}: {e}")
                continue
        
        # Clear the scraped_urls set for the next request
        scraped_urls.clear()
        return {"results": results}
    
    finally:
        # Ensure browser cleanup happens
        await cleanup_browser()

# Keep existing helper functions (extract_favicon, extract_title, etc.) unchanged