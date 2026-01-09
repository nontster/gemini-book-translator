"""
Kindle Web Reader - Browser automation for Kindle Cloud Reader
"""

import asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from pathlib import Path
import logging
import time
import os

logger = logging.getLogger(__name__)

# Kindle Web URL
KINDLE_WEB_URL = "https://read.amazon.com"

# Selectors for Kindle Web Reader (may need adjustment based on Amazon's UI changes)
SELECTORS = {
    "book_content": "#kindle-reader-container, #KindleReaderIFrame, .kindleReader",
    "next_page_button": "[aria-label='Next Page'], .nextPageButton, #kindleReader_pageTurnAreaRight",
    "prev_page_button": "[aria-label='Previous Page'], .prevPageButton, #kindleReader_pageTurnAreaLeft",
    "page_number": ".pageNumber, .currentPageNumber, #kindleReader_footer_pageNumber",
    "library": ".library, #library-section, [data-testid='library']",
    "book_list": ".book-item, .library-book, [data-testid='book-item']",
}


class KindleWebReader:
    """
    Browser automation class for Kindle Cloud Reader (read.amazon.com)
    """
    
    def __init__(self, headless: bool = False, screenshot_dir: str = "screenshots"):
        """
        Initialize the Kindle Web Reader.
        
        Args:
            headless (bool): Run browser in headless mode (default: False for login)
            screenshot_dir (str): Directory to save screenshots
        """
        self.headless = headless
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)
        
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.current_page_num = 0
        
    async def launch_browser(self) -> None:
        """
        Launch browser and navigate to Kindle Web.
        """
        logger.info("Launching browser...")
        
        self.playwright = await async_playwright().start()
        
        # Use chromium with persistent context for session persistence
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        self.page = await self.context.new_page()
        
        logger.info(f"Navigating to {KINDLE_WEB_URL}")
        await self.page.goto(KINDLE_WEB_URL, wait_until='networkidle')
        
    async def wait_for_login(self, timeout: int = 300) -> bool:
        """
        Wait for user to complete login manually.
        
        Args:
            timeout (int): Maximum wait time in seconds (default: 5 minutes)
            
        Returns:
            bool: True if login successful, False if timeout
        """
        logger.info("Please login to your Amazon account in the browser window...")
        logger.info(f"Waiting up to {timeout} seconds for login...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if we're on the library page (logged in)
            current_url = self.page.url
            
            if 'read.amazon.com' in current_url and '/library' in current_url.lower():
                logger.info("Login successful! Library page detected.")
                return True
            
            # Also check for reader page (user might have gone directly to a book)
            if 'read.amazon.com' in current_url and '/reader' in current_url.lower():
                logger.info("Login successful! Reader page detected.")
                return True
            
            # Check for book reader with ?asin= parameter
            if 'read.amazon.com' in current_url and 'asin=' in current_url.lower():
                logger.info("Login successful! Book reader detected (asin parameter).")
                return True
                
            # Check for library elements
            try:
                library_visible = await self.page.is_visible(SELECTORS["library"], timeout=1000)
                if library_visible:
                    logger.info("Login successful! Library visible.")
                    return True
            except:
                pass
            
            await asyncio.sleep(2)
        
        logger.error("Login timeout reached")
        return False
    
    async def wait_for_book_selection(self, timeout: int = 300) -> bool:
        """
        Wait for user to select a book from the library.
        
        Args:
            timeout (int): Maximum wait time in seconds
            
        Returns:
            bool: True if book is opened, False if timeout
        """
        logger.info("Please select a book from your library...")
        logger.info(f"Waiting up to {timeout} seconds for book selection...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_url = self.page.url
            
            # Check if we're on the reader page
            if '/reader' in current_url.lower():
                logger.info("Book opened! Reader page detected.")
                # Wait for content to load
                await asyncio.sleep(3)
                return True
            
            # Check for book reader with ?asin= parameter
            if 'read.amazon.com' in current_url and 'asin=' in current_url.lower():
                logger.info("Book opened! Book reader detected (asin parameter).")
                # Wait for content to load
                await asyncio.sleep(3)
                return True
            
            await asyncio.sleep(2)
        
        logger.error("Book selection timeout reached")
        return False
    
    async def capture_page(self, page_number: int = None) -> str:
        """
        Capture screenshot of the current page.
        
        Args:
            page_number (int): Optional page number for filename
            
        Returns:
            str: Path to the saved screenshot
        """
        if page_number is None:
            page_number = self.current_page_num
            
        filename = self.screenshot_dir / f"page_{page_number:04d}.png"
        
        # Try to capture just the reader content area
        try:
            # Wait for page to stabilize
            await asyncio.sleep(0.5)
            
            # Take full page screenshot
            await self.page.screenshot(path=str(filename), full_page=False)
            
            logger.info(f"Screenshot saved: {filename}")
            return str(filename)
            
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            raise
    
    async def next_page(self) -> bool:
        """
        Navigate to the next page.
        
        Returns:
            bool: True if navigation successful, False if at end
        """
        try:
            # Try keyboard navigation first (most reliable)
            await self.page.keyboard.press('ArrowRight')
            await asyncio.sleep(0.8)  # Wait for page turn animation
            
            self.current_page_num += 1
            logger.debug(f"Moved to page {self.current_page_num}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to navigate to next page: {e}")
            return False
    
    async def previous_page(self) -> bool:
        """
        Navigate to the previous page.
        
        Returns:
            bool: True if navigation successful
        """
        try:
            await self.page.keyboard.press('ArrowLeft')
            await asyncio.sleep(0.8)
            
            self.current_page_num = max(0, self.current_page_num - 1)
            logger.debug(f"Moved to page {self.current_page_num}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to navigate to previous page: {e}")
            return False
    
    async def get_current_page_info(self) -> dict:
        """
        Try to get current page information from the reader UI.
        
        Returns:
            dict: Page information (may be incomplete)
        """
        info = {
            "page_number": self.current_page_num,
            "page_text": None,
            "total_pages": None
        }
        
        try:
            # Try to get page number from UI
            page_num_element = await self.page.query_selector(SELECTORS["page_number"])
            if page_num_element:
                info["page_text"] = await page_num_element.text_content()
        except:
            pass
        
        return info
    
    async def is_last_page(self) -> bool:
        """
        Check if current page is the last page.
        Uses multiple heuristics for reliable detection.
        
        Returns:
            bool: True if likely last page
        """
        try:
            # Method 1: Check if next button is disabled
            next_btn = await self.page.query_selector(SELECTORS["next_page_button"])
            if next_btn:
                is_disabled = await next_btn.get_attribute('disabled')
                aria_disabled = await next_btn.get_attribute('aria-disabled')
                if is_disabled or aria_disabled == 'true':
                    logger.info("Last page detected: next button is disabled")
                    return True
            
            # Method 2: Check for end-of-book indicators in page content
            page_content = await self.page.content()
            end_indicators = [
                'end of book',
                'the end',
                'end of sample',
                'end of this sample',
                'last page',
                'ก่อนที่คุณจะไป',  # Thai "Before you go"
                'keep reading',
                'rate this book',
                'you\'ve reached the end',
            ]
            
            page_lower = page_content.lower()
            for indicator in end_indicators:
                if indicator in page_lower:
                    logger.info(f"Last page detected: found '{indicator}' in page")
                    return True
            
            # Method 3: Check for end-of-book overlay
            try:
                end_overlay = await self.page.query_selector('[class*="endOfBook"], [class*="end-of-book"], [data-testid="end-of-book"]')
                if end_overlay:
                    is_visible = await end_overlay.is_visible()
                    if is_visible:
                        logger.info("Last page detected: end-of-book overlay visible")
                        return True
            except:
                pass
                
        except Exception as e:
            logger.debug(f"Error checking for last page: {e}")
        
        return False
    
    async def check_page_changed(self, old_screenshot: bytes) -> bool:
        """
        Check if page content has changed by comparing screenshots.
        
        Args:
            old_screenshot (bytes): Previous screenshot data
            
        Returns:
            bool: True if page changed, False if same (likely last page)
        """
        try:
            import hashlib
            
            # Take new screenshot
            new_screenshot = await self.page.screenshot()
            
            # Compare hashes
            old_hash = hashlib.md5(old_screenshot).hexdigest()
            new_hash = hashlib.md5(new_screenshot).hexdigest()
            
            return old_hash != new_hash
            
        except Exception as e:
            logger.debug(f"Error comparing screenshots: {e}")
            return True  # Assume changed if error
    
    async def close(self) -> None:
        """
        Close the browser and cleanup.
        """
        logger.info("Closing browser...")
        
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
        logger.info("Browser closed")


async def main():
    """
    Test the Kindle Web Reader.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    
    reader = KindleWebReader(headless=False)
    
    try:
        await reader.launch_browser()
        
        if await reader.wait_for_login():
            print("\n✅ Login successful!")
            
            if await reader.wait_for_book_selection():
                print("\n✅ Book opened!")
                
                # Capture first few pages as a test
                for i in range(5):
                    screenshot_path = await reader.capture_page(i)
                    print(f"📸 Captured: {screenshot_path}")
                    
                    if not await reader.next_page():
                        print("Reached end of book or navigation failed")
                        break
                    
                print("\n✅ Test complete!")
        else:
            print("\n❌ Login failed or timeout")
            
    finally:
        await reader.close()


if __name__ == "__main__":
    asyncio.run(main())
