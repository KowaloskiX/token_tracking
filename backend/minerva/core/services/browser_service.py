# minerva/services/browser_service.py
from playwright.async_api import async_playwright, Browser, Playwright
from contextlib import asynccontextmanager
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BrowserService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.browser: Optional[Browser] = None
            self.playwright: Optional[Playwright] = None
            self.initialized = True

    async def initialize(self):
        """Initialize the browser service"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            logger.info("Browser service started successfully")

    async def cleanup(self):
        """Cleanup browser resources"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        logger.info("Browser service stopped")

    @asynccontextmanager
    async def create_context(self, **kwargs):
        """Create a new browser context with provided options"""
        if not self.browser:
            raise RuntimeError("Browser service not initialized")
        
        context = await self.browser.new_context(
            accept_downloads=True,
            **kwargs
        )
        try:
            yield context
        finally:
            await context.close()

# Create and export the instance
browser_service_instance = BrowserService()

# Make it available for import
__all__ = ['browser_service_instance']