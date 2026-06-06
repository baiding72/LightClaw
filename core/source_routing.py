"""Source routing hints for deciding when outside network tools are warranted."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SourceRouteDecision:
    route: str
    confidence: float
    reason: str
    local_hits: tuple[dict[str, object], ...] = ()

    def to_trace(self) -> dict[str, object]:
        return {
            "source_route": self.route,
            "source_route_confidence": round(self.confidence, 3),
            "source_route_reason": self.reason,
            "local_source_hits": list(self.local_hits),
        }


def infer_source_route(user_input: str, tool_name: str) -> SourceRouteDecision:
    if tool_name not in {"web_search", "read_url"}:
        return SourceRouteDecision("not_network_tool", 0.0, "不是联网工具")

    text = user_input.lower()
    current_year = str(datetime.now().year)
    freshness_markers = [
        "最新",
        "今天",
        "现在",
        "实时",
        "新闻",
        "价格",
        "官网",
        "网页",
        "互联网",
        "搜索",
        "查一下",
        "浏览",
        "today",
        "latest",
        "current",
        current_year,
    ]
    local_markers = [
        "myclaw",
        "cyberclaw",
        "当前项目",
        "这个项目",
        "本项目",
        "trace",
        "前面",
        "刚才",
        "会话",
        "workspace",
    ]

    freshness_score = sum(1 for marker in freshness_markers if marker in text)
    local_score = sum(1 for marker in local_markers if marker in text)
    if freshness_score > local_score:
        return SourceRouteDecision(
            "network_candidate",
            min(0.95, 0.55 + freshness_score * 0.1),
            "问题需要外部、实时或网页来源",
        )
    if local_score > 0:
        confidence = min(0.92, 0.55 + local_score * 0.08)
        return SourceRouteDecision(
            "local_first",
            confidence,
            "问题提到当前项目、会话或本地资料，应优先使用当前上下文、记忆或显式文件工具",
        )
    return SourceRouteDecision("unclear", 0.45, "没有足够信号判断是否需要联网")
