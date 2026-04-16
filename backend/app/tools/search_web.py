"""
搜索和网页工具
"""
import time
from typing import Any, Optional

from app.core.enums import FailureType
from app.schemas.tool import ToolParameter
from app.tools.base import BaseTool, ToolContext, ToolResult


class SearchWebTool(BaseTool):
    """搜索网页工具（Mock 实现）"""

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return "在网络上搜索信息。返回相关网页列表。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="搜索查询内容",
                required=True,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        query = args.get("query", "")
        if not query:
            return self.create_error_result(
                "搜索查询不能为空",
                FailureType.WRONG_ARGS,
            )

        # Mock 实现：返回模拟的搜索结果
        # TODO: 接入真实搜索引擎 API
        mock_results = [
            {
                "title": f"关于 {query} 的搜索结果 1",
                "url": f"https://example.com/search?q={query}&result=1",
                "snippet": f"这是关于 {query} 的第一条搜索结果摘要...",
            },
            {
                "title": f"关于 {query} 的搜索结果 2",
                "url": f"https://example.com/search?q={query}&result=2",
                "snippet": f"这是关于 {query} 的第二条搜索结果摘要...",
            },
            {
                "title": f"关于 {query} 的搜索结果 3",
                "url": f"https://example.com/search?q={query}&result=3",
                "snippet": f"这是关于 {query} 的第三条搜索结果摘要...",
            },
        ]

        latency_ms = int((time.time() - start_time) * 1000)

        return self.create_success_result(
            {
                "query": query,
                "results": mock_results,
                "total": len(mock_results),
                "note": "这是模拟的搜索结果，真实实现请接入搜索引擎 API",
            },
            latency_ms=latency_ms,
        )


class OpenUrlTool(BaseTool):
    """打开 URL 工具"""

    @property
    def name(self) -> str:
        return "open_url"

    @property
    def description(self) -> str:
        return "打开指定的 URL 地址。返回页面标题和基本信息。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="要打开的 URL 地址",
                required=True,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        url = args.get("url", "")
        if not url:
            return self.create_error_result(
                "URL 不能为空",
                FailureType.WRONG_ARGS,
            )

        # 如果有浏览器页面，使用 Playwright 打开
        if context.browser_page:
            try:
                await context.browser_page.goto(url)
                title = await context.browser_page.title()
                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_success_result(
                    {
                        "url": url,
                        "title": title,
                        "status": "loaded",
                    },
                    latency_ms=latency_ms,
                )
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_error_result(
                    f"打开页面失败: {str(e)}",
                    FailureType.TOOL_RUNTIME_ERROR,
                    latency_ms=latency_ms,
                )

        # Mock 实现
        latency_ms = int((time.time() - start_time) * 1000)
        return self.create_success_result(
            {
                "url": url,
                "title": f"页面标题 - {url}",
                "status": "loaded (mock)",
                "note": "这是模拟的页面加载结果",
            },
            latency_ms=latency_ms,
        )


class ReadPageTool(BaseTool):
    """读取页面内容工具"""

    @property
    def name(self) -> str:
        return "read_page"

    @property
    def description(self) -> str:
        return "读取当前页面的正文内容。"

    @property
    def category(self) -> str:
        return "information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="selector",
                type="string",
                description="可选，要读取的内容区域选择器",
                required=False,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        # 如果有浏览器页面，使用 Playwright 读取
        if context.browser_page:
            try:
                selector = args.get("selector", "body")
                element = await context.browser_page.query_selector(selector)
                if element:
                    content = await element.inner_text()
                    latency_ms = int((time.time() - start_time) * 1000)
                    return self.create_success_result(
                        {
                            "content": content[:5000],  # 限制长度
                            "length": len(content),
                            "selector": selector,
                        },
                        latency_ms=latency_ms,
                    )
                else:
                    latency_ms = int((time.time() - start_time) * 1000)
                    return self.create_error_result(
                        f"未找到选择器 {selector} 对应的元素",
                        FailureType.GUI_WRONG_ELEMENT,
                        latency_ms=latency_ms,
                    )
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                return self.create_error_result(
                    f"读取页面失败: {str(e)}",
                    FailureType.TOOL_RUNTIME_ERROR,
                    latency_ms=latency_ms,
                )

        # Mock 实现
        latency_ms = int((time.time() - start_time) * 1000)
        return self.create_success_result(
            {
                "content": "这是模拟的页面内容。\n\n页面正文内容...",
                "length": 100,
                "note": "这是模拟的页面读取结果",
            },
            latency_ms=latency_ms,
        )
