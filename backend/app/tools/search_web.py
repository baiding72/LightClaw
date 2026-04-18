"""
搜索和网页工具
"""
from __future__ import annotations

import asyncio
import time
from html import unescape
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse, urlunparse
from xml.etree import ElementTree

import httpx

from app.core.config import get_settings
from app.core.enums import FailureType
from app.schemas.tool import ToolParameter
from app.tools.base import BaseTool, ToolContext, ToolResult


DUCKDUCKGO_HTML_URL = "https://lite.duckduckgo.com/lite/"
WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/title"
BING_RSS_SEARCH_URL = "https://www.bing.com/search"
SEARCH_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)


class DuckDuckGoHTMLParser(HTMLParser):
    """轻量 DuckDuckGo HTML 结果解析器"""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._capture_title = False
        self._capture_snippet = False
        self._current_title_parts: list[str] = []
        self._current_snippet_parts: list[str] = []
        self._current_url: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attrs_map = dict(attrs)
        class_name = attrs_map.get("class", "") or ""

        if tag == "a" and ("result__a" in class_name or "result-link" in class_name):
            self._capture_title = True
            self._current_title_parts = []
            self._current_url = attrs_map.get("href")
            return

        if tag in {"a", "div", "td"} and ("result__snippet" in class_name or "result-snippet" in class_name):
            self._capture_snippet = True
            self._current_snippet_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            title = self._clean_text("".join(self._current_title_parts))
            url = normalize_search_result_url(self._current_url or "")
            if title and url:
                self.results.append({
                    "title": title,
                    "url": url,
                    "snippet": "",
                })
            self._capture_title = False
            self._current_title_parts = []
            self._current_url = None
            return

        if tag in {"a", "div", "td"} and self._capture_snippet:
            snippet = self._clean_text("".join(self._current_snippet_parts))
            if snippet and self.results and not self.results[-1]["snippet"]:
                self.results[-1]["snippet"] = snippet
            self._capture_snippet = False
            self._current_snippet_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._current_title_parts.append(data)
        elif self._capture_snippet:
            self._current_snippet_parts.append(data)

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(unescape(value).split())


def normalize_search_result_url(raw_url: str) -> str:
    """规范化搜索结果 URL，用于去重和展示"""
    if not raw_url:
        return ""

    decoded_url = unescape(raw_url.strip())
    if decoded_url.startswith("//"):
        decoded_url = f"https:{decoded_url}"

    parsed = urlparse(decoded_url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target_url = parse_qs(parsed.query).get("uddg", [""])[0]
        if target_url:
            decoded_url = unquote(target_url)
            parsed = urlparse(decoded_url)

    if not parsed.scheme:
        decoded_url = f"https://{decoded_url.lstrip('/')}"
        parsed = urlparse(decoded_url)

    filtered_query = []
    for key, value in parse_qs(parsed.query, keep_blank_values=False).items():
        if key.lower().startswith("utm_"):
            continue
        filtered_query.extend((key, item) for item in value)

    canonical_query = "&".join(
        f"{quote_plus(key)}={quote_plus(item)}" for key, item in sorted(filtered_query)
    )
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=canonical_query,
        fragment="",
    )
    return urlunparse(normalized)


def deduplicate_search_results(results: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    """按规范化 URL 去重"""
    seen_urls: set[str] = set()
    deduplicated: list[dict[str, str]] = []

    for result in results:
        normalized_url = normalize_search_result_url(result.get("url", ""))
        parsed_url = urlparse(normalized_url)

        if (
            not normalized_url
            or normalized_url in seen_urls
            or (
                parsed_url.netloc.endswith("duckduckgo.com")
                and parsed_url.path not in {"", "/"}
            )
        ):
            continue

        seen_urls.add(normalized_url)
        deduplicated.append({
            "title": result.get("title", "").strip(),
            "url": normalized_url,
            "snippet": result.get("snippet", "").strip(),
            "source": result.get("source", ""),
        })

        if len(deduplicated) >= limit:
            break

    return deduplicated


class SearchWebTool(BaseTool):
    """真实网页搜索工具"""

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return "在网络上搜索信息。返回相关网页标题、摘要和 URL。"

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
            ToolParameter(
                name="site",
                type="string",
                description="可选，限定搜索站点，例如 openai.com",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="可选，最多返回多少条结果",
                required=False,
                default=get_settings().search_max_results,
                min_value=1,
                max_value=10,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()
        query_value = args.get("query", "")
        query = query_value.strip() if isinstance(query_value, str) else ""
        site_value = args.get("site")
        site = site_value.strip() if isinstance(site_value, str) else ""

        if not query:
            return self.create_error_result(
                "搜索查询不能为空",
                FailureType.WRONG_ARGS,
            )

        settings = get_settings()
        raw_limit = args.get("limit", settings.search_max_results)
        limit_value = raw_limit if isinstance(raw_limit, int) else settings.search_max_results
        limit = min(10, max(1, limit_value))
        search_query = f"site:{site} {query}".strip() if site else query

        try:
            if settings.search_provider == "mock":
                results = self._mock_search(search_query, limit)
            else:
                results = await self._search(query=search_query, limit=limit, site=site or None)
            latency_ms = int((time.time() - start_time) * 1000)

            return self.create_success_result(
                {
                    "query": query,
                    "effective_query": search_query,
                    "site": site or None,
                    "provider": settings.search_provider,
                    "results": results,
                    "total": len(results),
                    "deduplicated": True,
                },
                latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.time() - start_time) * 1000)
            return self.create_error_result(
                f"搜索失败: {exc}",
                FailureType.TOOL_RUNTIME_ERROR,
                latency_ms=latency_ms,
            )

    async def _search(self, query: str, limit: int, site: Optional[str] = None) -> list[dict[str, str]]:
        settings = get_settings()

        async with httpx.AsyncClient(
            timeout=settings.search_timeout,
            follow_redirects=True,
            headers={"User-Agent": SEARCH_USER_AGENT},
        ) as client:
            try:
                duckduckgo_results = await self._search_duckduckgo(client, query, limit)
                if duckduckgo_results:
                    return duckduckgo_results
            except Exception:
                # DuckDuckGo 是主路径，失败后继续走回退源。
                pass

            bing_results = await self._search_bing_rss(client, query, limit)
            if bing_results:
                return bing_results

            wikipedia_results = await self._search_wikipedia(client, query, limit, site=site)
            if wikipedia_results:
                return wikipedia_results

        raise RuntimeError("没有从搜索源返回可用结果")

    async def _search_duckduckgo(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
    ) -> list[dict[str, str]]:
        response = await self._request_with_retry(
            client,
            DUCKDUCKGO_HTML_URL,
            method="GET",
            params={"q": query},
            accept_statuses={200},
        )
        parser = DuckDuckGoHTMLParser()
        parser.feed(response.text)
        parsed_results = [
            {
                **item,
                "source": "duckduckgo",
            }
            for item in parser.results
        ]
        return deduplicate_search_results(parsed_results, limit)

    async def _search_wikipedia(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
        site: Optional[str] = None,
    ) -> list[dict[str, str]]:
        if site and "wikipedia.org" not in site.lower():
            return []
        response = await self._request_with_retry(
            client,
            WIKIPEDIA_SEARCH_URL,
            method="GET",
            params={"q": query, "limit": limit},
            accept_statuses={200},
        )
        payload = response.json()
        pages = payload.get("pages", [])
        results = []

        for page in pages:
            page_key = page.get("key")
            if not page_key:
                continue

            results.append({
                "title": page.get("title", page_key),
                "url": f"https://en.wikipedia.org/wiki/{quote_plus(page_key.replace(' ', '_'))}",
                "snippet": page.get("description") or page.get("excerpt") or "",
                "source": "wikipedia",
            })

        return deduplicate_search_results(results, limit)

    async def _search_bing_rss(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
    ) -> list[dict[str, str]]:
        response = await self._request_with_retry(
            client,
            BING_RSS_SEARCH_URL,
            method="GET",
            params={"q": query, "format": "rss"},
            accept_statuses={200},
        )

        root = ElementTree.fromstring(response.text)
        channel = root.find("channel")
        if channel is None:
            return []

        results = []
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            snippet = (item.findtext("description") or "").strip()
            if not title or not url:
                continue
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": "bing_rss",
            })

        return deduplicate_search_results(results, limit)

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        method: str,
        *,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        accept_statuses: Optional[set[int]] = None,
    ) -> httpx.Response:
        settings = get_settings()
        last_error: Optional[Exception] = None
        accepted = accept_statuses or {200}

        for attempt in range(1, settings.search_retry_count + 1):
            try:
                response = await client.request(method, url, params=params, data=data)
                if response.status_code not in accepted:
                    raise RuntimeError(f"{url} returned status {response.status_code}")
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == settings.search_retry_count:
                    break
                await asyncio.sleep(0.4 * attempt)

        raise RuntimeError(str(last_error) if last_error else f"Request failed: {url}")

    def _mock_search(self, query: str, limit: int) -> list[dict[str, str]]:
        mock_results = [
            {
                "title": f"关于 {query} 的搜索结果 {index}",
                "url": f"https://example.com/search?q={quote_plus(query)}&result={index}",
                "snippet": f"这是关于 {query} 的第 {index} 条搜索结果摘要...",
                "source": "mock",
            }
            for index in range(1, limit + 1)
        ]
        return mock_results


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
