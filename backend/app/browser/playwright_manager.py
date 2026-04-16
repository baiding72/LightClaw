"""
Playwright 浏览器管理器
"""
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from app.core.config import get_settings
from app.core.logger import logger


class PlaywrightManager:
    """Playwright 浏览器管理器"""

    def __init__(self):
        self.settings = get_settings()
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def start(self) -> None:
        """启动浏览器"""
        if self._browser:
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.settings.headless_browser,
            timeout=self.settings.browser_timeout,
        )

        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="zh-CN",
        )

        self._page = await self._context.new_page()

        logger.info("Playwright browser started")

    async def close(self) -> None:
        """关闭浏览器"""
        if self._page:
            await self._page.close()
            self._page = None

        if self._context:
            await self._context.close()
            self._context = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("Playwright browser closed")

    @property
    def page(self) -> Optional[Page]:
        """获取当前页面"""
        return self._page

    async def new_page(self) -> Page:
        """创建新页面"""
        if not self._context:
            await self.start()

        return await self._context.new_page()

    async def goto(self, url: str) -> None:
        """导航到 URL"""
        if not self._page:
            await self.start()

        await self._page.goto(url)
        logger.info(f"Navigated to: {url}")

    async def take_screenshot(self, path: str, full_page: bool = False) -> str:
        """截图"""
        if not self._page:
            raise RuntimeError("No page available")

        await self._page.screenshot(path=path, full_page=full_page)
        logger.info(f"Screenshot saved: {path}")
        return path

    async def get_content(self) -> str:
        """获取页面内容"""
        if not self._page:
            raise RuntimeError("No page available")

        return await self._page.content()

    async def get_title(self) -> str:
        """获取页面标题"""
        if not self._page:
            raise RuntimeError("No page available")

        return await self._page.title()

    async def click(self, selector: str) -> bool:
        """点击元素"""
        if not self._page:
            raise RuntimeError("No page available")

        try:
            await self._page.click(selector, timeout=5000)
            logger.info(f"Clicked: {selector}")
            return True
        except Exception as e:
            logger.warning(f"Click failed: {selector}, error: {e}")
            return False

    async def type_text(self, selector: str, text: str, clear: bool = True) -> bool:
        """输入文本"""
        if not self._page:
            raise RuntimeError("No page available")

        try:
            if clear:
                await self._page.fill(selector, text)
            else:
                await self._page.type(selector, text)
            logger.info(f"Typed into: {selector}")
            return True
        except Exception as e:
            logger.warning(f"Type failed: {selector}, error: {e}")
            return False

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> bool:
        """等待元素出现"""
        if not self._page:
            raise RuntimeError("No page available")

        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False


# 全局管理器
_manager: Optional[PlaywrightManager] = None


async def get_browser_manager() -> PlaywrightManager:
    """获取浏览器管理器单例"""
    global _manager
    if _manager is None:
        _manager = PlaywrightManager()
        await _manager.start()
    return _manager


async def close_browser_manager() -> None:
    """关闭浏览器管理器"""
    global _manager
    if _manager:
        await _manager.close()
        _manager = None
