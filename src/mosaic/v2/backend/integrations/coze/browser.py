"""
Coze Browser Manager
====================

Provides browser connection and lifecycle management for Coze platform automation
using Playwright and Chrome DevTools Protocol (CDP).

BrowserManager is a singleton that connects to an already-running Chrome instance
via CDP, preserving user session and authentication.

Browser must be started with remote debugging:
    chrome --remote-debugging-port=19222 --user-data-dir=/tmp/chrome-coze
"""

import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from .exceptions import CozeConnectionError


logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Singleton browser connection manager for Coze platform automation.

    Manages browser lifecycle via CDP (Chrome DevTools Protocol) and provides
    page management for Coze operations.
    """

    _instance: Optional['BrowserManager'] = None
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _page: Optional[Page] = None
    _cdp_url: Optional[str] = None

    def __new__(cls):
        """
        Ensure only one BrowserManager instance exists.

        Returns:
            BrowserManager: The singleton instance
        """
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
            logger.info("BrowserManager singleton instance created")
        return cls._instance

    async def connect(self, cdp_url: str = "http://192.168.1.4:19222") -> Browser:
        """
        Connect to browser via CDP protocol.

        Attaches to an already-running Chrome instance with remote debugging enabled.
        Reuses existing browser contexts and pages to preserve session state.

        Args:
            cdp_url: Chrome DevTools Protocol endpoint URL

        Returns:
            Browser: Connected Playwright browser instance

        Raises:
            CozeConnectionError: If browser connection fails or is unreachable
            TimeoutError: If connection takes too long
        """
        # If already connected to the same URL, return existing browser
        if self._browser and self._cdp_url == cdp_url:
            if await self.is_connected():
                logger.info(f"Reusing existing connection to {cdp_url}")
                return self._browser
            else:
                logger.warning("Existing connection is dead, reconnecting...")
                await self.close()

        try:
            logger.info(f"Connecting to browser at {cdp_url}...")

            # Start Playwright instance
            self._playwright = await async_playwright().start()

            # Connect to browser via CDP
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)

            # Get the default context (reuse existing session)
            contexts = self._browser.contexts
            if not contexts:
                raise CozeConnectionError(
                    f"No browser contexts found at {cdp_url}. "
                    "Browser may have been started without a profile."
                )

            self._context = contexts[0]

            # Get or create page
            pages = self._context.pages
            if pages:
                self._page = pages[0]
                logger.info(f"Reusing existing page: {self._page.url}")
            else:
                self._page = await self._context.new_page()
                logger.info("Created new page")

            self._cdp_url = cdp_url
            logger.info(f"Successfully connected to browser at {cdp_url}")

            return self._browser

        except Exception as e:
            error_msg = str(e)

            if "ECONNREFUSED" in error_msg or "Connection refused" in error_msg:
                raise CozeConnectionError(
                    f"Browser not running on {cdp_url}. "
                    "Start browser with: chrome --remote-debugging-port=19222"
                )
            elif "timeout" in error_msg.lower():
                raise TimeoutError(f"Connection timeout to {cdp_url}")
            else:
                raise CozeConnectionError(f"Failed to connect to browser: {error_msg}")

    async def get_page(self) -> Page:
        """
        Get or create a page for Coze operations.

        Reuses existing page if available, creates new one if needed.
        Automatically connects to browser if not already connected.

        Returns:
            Page: Playwright page instance ready for use

        Raises:
            CozeConnectionError: If browser is not connected
        """
        # Auto-connect if not connected
        if not self._browser or not await self.is_connected():
            logger.info("Browser not connected, connecting automatically...")
            await self.connect()

        # Return existing page if available
        if self._page and not self._page.is_closed():
            return self._page

        # Create new page if needed
        if not self._context:
            raise CozeConnectionError("Browser context is not available")

        self._page = await self._context.new_page()
        logger.info("Created new page")

        return self._page

    async def navigate_to_skills(self, page: Page) -> None:
        """
        Navigate to Coze skills marketplace page.

        Args:
            page: Playwright page instance

        Target URL: https://www.coze.cn/skills
        """
        target_url = "https://www.coze.cn/skills"

        # Skip navigation if already on the page
        if target_url in page.url:
            logger.info(f"Already on skills page: {page.url}")
            return

        logger.info(f"Navigating to {target_url}...")
        await page.goto(target_url)
        await page.wait_for_load_state("networkidle")
        logger.info(f"Successfully navigated to {target_url}")

    async def is_connected(self) -> bool:
        """
        Check if browser connection is alive.

        Returns:
            bool: True if connected and responsive, False otherwise
        """
        if not self._browser:
            return False

        try:
            # Check if browser is still connected
            return self._browser.is_connected()
        except Exception as e:
            logger.warning(f"Connection check failed: {e}")
            return False

    async def close(self) -> None:
        """
        Close browser connection and cleanup resources.

        Closes all managed pages, disconnects from browser (without closing the
        browser itself), stops Playwright, and resets singleton instance.
        """
        logger.info("Closing browser connection...")

        # Close page if exists
        if self._page and not self._page.is_closed():
            try:
                await self._page.close()
                logger.info("Closed page")
            except Exception as e:
                logger.warning(f"Failed to close page: {e}")

        # Disconnect from browser (don't close it, just disconnect)
        if self._browser:
            try:
                await self._browser.close()
                logger.info("Disconnected from browser")
            except Exception as e:
                logger.warning(f"Failed to disconnect from browser: {e}")

        # Stop Playwright instance
        if self._playwright:
            try:
                await self._playwright.stop()
                logger.info("Stopped Playwright")
            except Exception as e:
                logger.warning(f"Failed to stop Playwright: {e}")

        # Reset instance variables
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._cdp_url = None

        logger.info("Browser connection closed successfully")
