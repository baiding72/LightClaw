"""
浏览器动作执行
"""
from typing import Any, Optional

from playwright.async_api import Page

from app.core.logger import logger


class BrowserActions:
    """浏览器动作执行器"""

    def __init__(self, page: Page):
        self.page = page

    async def click(self, selector: str, timeout: int = 5000) -> dict[str, Any]:
        """点击元素"""
        try:
            await self.page.click(selector, timeout=timeout)
            return {"success": True, "action": "click", "selector": selector}
        except Exception as e:
            return {"success": False, "action": "click", "selector": selector, "error": str(e)}

    async def type_text(
        self,
        selector: str,
        text: str,
        clear: bool = True,
        timeout: int = 5000,
    ) -> dict[str, Any]:
        """输入文本"""
        try:
            if clear:
                await self.page.fill(selector, text, timeout=timeout)
            else:
                await self.page.type(selector, text)
            return {"success": True, "action": "type", "selector": selector, "text": text}
        except Exception as e:
            return {"success": False, "action": "type", "selector": selector, "error": str(e)}

    async def select_option(
        self,
        selector: str,
        value: str,
        timeout: int = 5000,
    ) -> dict[str, Any]:
        """选择下拉选项"""
        try:
            await self.page.select_option(selector, value, timeout=timeout)
            return {"success": True, "action": "select", "selector": selector, "value": value}
        except Exception as e:
            return {"success": False, "action": "select", "selector": selector, "error": str(e)}

    async def scroll(self, direction: str = "down", amount: int = 300) -> dict[str, Any]:
        """滚动页面"""
        try:
            delta = -amount if direction == "up" else amount
            await self.page.mouse.wheel(0, delta)
            return {"success": True, "action": "scroll", "direction": direction}
        except Exception as e:
            return {"success": False, "action": "scroll", "error": str(e)}

    async def navigate(self, url: str, timeout: int = 30000) -> dict[str, Any]:
        """导航到 URL"""
        try:
            await self.page.goto(url, timeout=timeout)
            title = await self.page.title()
            return {"success": True, "action": "navigate", "url": url, "title": title}
        except Exception as e:
            return {"success": False, "action": "navigate", "url": url, "error": str(e)}

    async def wait_for_element(self, selector: str, timeout: int = 5000) -> dict[str, Any]:
        """等待元素出现"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "action": "wait", "selector": selector}
        except Exception as e:
            return {"success": False, "action": "wait", "selector": selector, "error": str(e)}

    async def get_text(self, selector: str, timeout: int = 5000) -> dict[str, Any]:
        """获取元素文本"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                text = await element.inner_text()
                return {"success": True, "action": "get_text", "selector": selector, "text": text}
            return {"success": False, "action": "get_text", "selector": selector, "error": "Element not found"}
        except Exception as e:
            return {"success": False, "action": "get_text", "selector": selector, "error": str(e)}
