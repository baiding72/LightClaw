"""
浏览器交互工具
"""
import time
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_settings
from app.core.enums import FailureType
from app.schemas.tool import ToolParameter
from app.tools.base import BaseTool, ToolContext, ToolResult


class ClickTool(BaseTool):
    """点击元素工具"""

    @property
    def name(self) -> str:
        return "click"

    @property
    def description(self) -> str:
        return "在当前页面上点击指定的元素。"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="selector",
                type="string",
                description="要点击的元素的 CSS 选择器或文本描述",
                required=True,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        selector = args.get("selector", "")
        if not selector:
            return self.create_error_result(
                "元素选择器不能为空",
                FailureType.WRONG_ARGS,
            )

        # 如果有浏览器页面，执行真实点击
        if context.browser_page:
            try:
                await context.browser_page.click(selector)
                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_success_result(
                    {
                        "action": "click",
                        "selector": selector,
                        "status": "success",
                    },
                    latency_ms=latency_ms,
                )
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_error_result(
                    f"点击元素失败: {str(e)}",
                    FailureType.GUI_CLICK_MISS,
                    latency_ms=latency_ms,
                )

        # Mock 实现
        latency_ms = int((time.time() - start_time) * 1000)
        return self.create_success_result(
            {
                "action": "click",
                "selector": selector,
                "status": "success (mock)",
            },
            latency_ms=latency_ms,
        )


class TypeTextTool(BaseTool):
    """输入文本工具"""

    @property
    def name(self) -> str:
        return "type_text"

    @property
    def description(self) -> str:
        return "在指定的输入框中输入文本。"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="selector",
                type="string",
                description="输入框的 CSS 选择器",
                required=True,
            ),
            ToolParameter(
                name="text",
                type="string",
                description="要输入的文本内容",
                required=True,
            ),
            ToolParameter(
                name="clear_first",
                type="boolean",
                description="是否先清空输入框",
                required=False,
                default=True,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        selector = args.get("selector", "")
        text = args.get("text", "")
        clear_first = args.get("clear_first", True)

        if not selector:
            return self.create_error_result(
                "元素选择器不能为空",
                FailureType.WRONG_ARGS,
            )

        if not text:
            return self.create_error_result(
                "输入文本不能为空",
                FailureType.WRONG_ARGS,
            )

        # 如果有浏览器页面，执行真实输入
        if context.browser_page:
            try:
                if clear_first:
                    await context.browser_page.fill(selector, text)
                else:
                    await context.browser_page.type(selector, text)

                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_success_result(
                    {
                        "action": "type",
                        "selector": selector,
                        "text": text,
                        "status": "success",
                    },
                    latency_ms=latency_ms,
                )
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_error_result(
                    f"输入文本失败: {str(e)}",
                    FailureType.GUI_WRONG_ELEMENT,
                    latency_ms=latency_ms,
                )

        # Mock 实现
        latency_ms = int((time.time() - start_time) * 1000)
        return self.create_success_result(
            {
                "action": "type",
                "selector": selector,
                "text": text,
                "status": "success (mock)",
            },
            latency_ms=latency_ms,
        )


class ScrollTool(BaseTool):
    """滚动页面工具"""

    @property
    def name(self) -> str:
        return "scroll"

    @property
    def description(self) -> str:
        return "滚动当前页面。"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="direction",
                type="string",
                description="滚动方向：up 或 down",
                required=False,
                enum=["up", "down"],
                default="down",
            ),
            ToolParameter(
                name="amount",
                type="string",
                description="滚动量：page（一页）或 pixels（像素）",
                required=False,
                enum=["page", "pixels"],
                default="page",
            ),
            ToolParameter(
                name="pixels",
                type="integer",
                description="如果 amount 为 pixels，滚动的像素数",
                required=False,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        direction = args.get("direction", "down")
        amount = args.get("amount", "page")
        pixels = args.get("pixels", 300)

        # 如果有浏览器页面，执行真实滚动
        if context.browser_page:
            try:
                if amount == "page":
                    delta = -500 if direction == "up" else 500
                    await context.browser_page.mouse.wheel(0, delta)
                else:
                    delta = -pixels if direction == "up" else pixels
                    await context.browser_page.mouse.wheel(0, delta)

                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_success_result(
                    {
                        "action": "scroll",
                        "direction": direction,
                        "amount": amount,
                        "status": "success",
                    },
                    latency_ms=latency_ms,
                )
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_error_result(
                    f"滚动页面失败: {str(e)}",
                    FailureType.TOOL_RUNTIME_ERROR,
                    latency_ms=latency_ms,
                )

        # Mock 实现
        latency_ms = int((time.time() - start_time) * 1000)
        return self.create_success_result(
            {
                "action": "scroll",
                "direction": direction,
                "amount": amount,
                "status": "success (mock)",
            },
            latency_ms=latency_ms,
        )


class TakeScreenshotTool(BaseTool):
    """截图工具"""

    @property
    def name(self) -> str:
        return "take_screenshot"

    @property
    def description(self) -> str:
        return "截取当前页面的屏幕截图。"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="full_page",
                type="boolean",
                description="是否截取完整页面（包括滚动区域）",
                required=False,
                default=False,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        full_page = args.get("full_page", False)

        # 如果有浏览器页面，执行真实截图
        if context.browser_page:
            try:
                settings = get_settings()

                # 生成截图文件名
                screenshot_dir = Path(context.screenshot_dir or settings.screenshots_dir)
                screenshot_dir.mkdir(parents=True, exist_ok=True)

                filename = f"screenshot_{context.task_id}_{context.step_index}.png"
                screenshot_path = screenshot_dir / filename

                await context.browser_page.screenshot(
                    path=str(screenshot_path),
                    full_page=full_page,
                )

                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_success_result(
                    {
                        "action": "screenshot",
                        "path": str(screenshot_path),
                        "status": "success",
                    },
                    latency_ms=latency_ms,
                    screenshot_path=str(screenshot_path),
                )
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_error_result(
                    f"截图失败: {str(e)}",
                    FailureType.TOOL_RUNTIME_ERROR,
                    latency_ms=latency_ms,
                )

        # Mock 实现
        latency_ms = int((time.time() - start_time) * 1000)
        return self.create_success_result(
            {
                "action": "screenshot",
                "path": f"screenshots/mock_{context.task_id}_{context.step_index}.png",
                "status": "success (mock)",
            },
            latency_ms=latency_ms,
        )


class SelectOptionTool(BaseTool):
    """选择下拉选项工具"""

    @property
    def name(self) -> str:
        return "select_option"

    @property
    def description(self) -> str:
        return "在下拉选择框中选择一个选项。"

    @property
    def category(self) -> str:
        return "browser"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="selector",
                type="string",
                description="下拉选择框的 CSS 选择器",
                required=True,
            ),
            ToolParameter(
                name="option",
                type="string",
                description="要选择的选项值或文本",
                required=True,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        selector = args.get("selector", "")
        option = args.get("option", "")

        if not selector:
            return self.create_error_result(
                "元素选择器不能为空",
                FailureType.WRONG_ARGS,
            )

        if not option:
            return self.create_error_result(
                "选项不能为空",
                FailureType.WRONG_ARGS,
            )

        # 如果有浏览器页面，执行真实选择
        if context.browser_page:
            try:
                await context.browser_page.select_option(selector, option)

                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_success_result(
                    {
                        "action": "select",
                        "selector": selector,
                        "option": option,
                        "status": "success",
                    },
                    latency_ms=latency_ms,
                )
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_error_result(
                    f"选择选项失败: {str(e)}",
                    FailureType.GUI_WRONG_ELEMENT,
                    latency_ms=latency_ms,
                )

        # Mock 实现
        latency_ms = int((time.time() - start_time) * 1000)
        return self.create_success_result(
            {
                "action": "select",
                "selector": selector,
                "option": option,
                "status": "success (mock)",
            },
            latency_ms=latency_ms,
        )
