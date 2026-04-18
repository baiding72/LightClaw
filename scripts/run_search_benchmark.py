#!/usr/bin/env python3
"""
搜索能力对比 benchmark

对比 mock 搜索和真实搜索下的信息整理任务成功率。
"""
from __future__ import annotations

import asyncio
import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.tools.base import ToolContext
from app.tools.search_web import SearchWebTool


BENCHMARK_CASES = [
    {
        "task_id": "info_004",
        "instruction": "搜索关于人工智能最新发展的信息，整理成笔记。",
        "query": "latest artificial intelligence developments",
        "site": "",
    },
    {
        "task_id": "info_005",
        "instruction": "从多个网页中收集产品价格信息，创建对比笔记。",
        "query": "MacBook Air M4 price comparison",
        "site": "",
    },
    {
        "task_id": "custom_openai_news",
        "instruction": "整理 OpenAI 最新产品发布信息。",
        "query": "OpenAI latest product announcements",
        "site": "openai.com",
    },
]


@contextmanager
def temporary_search_provider(provider: str):
    settings = get_settings()
    previous = settings.search_provider
    settings.search_provider = provider
    try:
        yield
    finally:
        settings.search_provider = previous


async def fetch_first_result_summary(url: str) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "LightClaw Search Benchmark/0.1"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            title_start = response.text.lower().find("<title>")
            title_end = response.text.lower().find("</title>")
            if title_start >= 0 and title_end > title_start:
                title = response.text[title_start + 7:title_end].strip()
            else:
                title = "title_not_found"
            return True, title[:120]
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


async def run_case(provider: str, case: dict[str, str]) -> dict:
    tool = SearchWebTool()
    ctx = ToolContext(task_id=case["task_id"], step_index=1, trajectory_id=f"traj_{provider}")
    result = await tool.execute(
        {
            "query": case["query"],
            "site": case["site"] or None,
            "limit": 3,
        },
        ctx,
    )

    payload = result.result or {}
    search_results = payload.get("results") or []
    first_result = search_results[0] if search_results else None

    fetch_success = False
    fetch_details = ""
    if first_result:
        fetch_success, fetch_details = await fetch_first_result_summary(first_result["url"])

    is_success = bool(result.success and first_result and fetch_success)

    return {
        "task_id": case["task_id"],
        "instruction": case["instruction"],
        "provider": provider,
        "query": case["query"],
        "site": case["site"] or None,
        "search_success": result.success,
        "results_count": len(search_results),
        "first_result": first_result,
        "fetch_success": fetch_success,
        "fetch_details": fetch_details,
        "is_success": is_success,
    }


async def main() -> None:
    output_dir = BACKEND_DIR / "data" / "eval"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, list[dict]] = {}
    print("=" * 60)
    print("LightClaw Search Benchmark")
    print("=" * 60)

    for provider in ["mock", "duckduckgo"]:
        with temporary_search_provider(provider):
            provider_results = []
            for case in BENCHMARK_CASES:
                case_result = await run_case(provider, case)
                provider_results.append(case_result)
                status = "SUCCESS" if case_result["is_success"] else "FAILED"
                print(f"[{provider}] {case['task_id']}: {status}")
                if case_result["first_result"]:
                    print(f"  -> {case_result['first_result']['title']}")
                    print(f"  -> {case_result['first_result']['url']}")
            all_results[provider] = provider_results

    summary = {}
    for provider, provider_results in all_results.items():
        success_count = sum(1 for item in provider_results if item["is_success"])
        summary[provider] = {
            "total_tasks": len(provider_results),
            "successful_tasks": success_count,
            "task_success_rate": success_count / len(provider_results) if provider_results else 0.0,
        }

    print("\nSummary")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"search_benchmark_{timestamp}.json"
    output_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "cases": all_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
