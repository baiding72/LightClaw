#!/usr/bin/env python3
"""
求职投递闭环 smoke test

流程：
1. 创建一条 application tracker 记录
2. 搜索目标公司的岗位/招聘入口
3. 打开结果页并读取正文
4. 回写下一步动作
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.browser import close_browser_manager
from app.db import setup_database
from app.db.session import async_session_maker
from app.runtime.executor import Executor
from app.runtime.state import AgentState
from app.schemas.job_application import ApplicationCreate, ApplicationUpdate
from app.services.application_service import ApplicationService
from app.tools.base import ToolContext
from app.tools.search_web import SearchWebTool


async def main() -> None:
    await setup_database()

    async with async_session_maker() as session:
        service = ApplicationService(session)
        record = await service.create_application(
            ApplicationCreate(
                company_name="OpenAI",
                role_title="Software Engineer Intern",
                status="discovered",
                notes="Smoke test record for the job application loop.",
                next_action="Search for official careers page and review role requirements.",
            )
        )

        search_tool = SearchWebTool()
        search_result = await search_tool.execute(
            {
                "query": "OpenAI careers software engineer intern",
                "site": "openai.com",
                "limit": 3,
            },
            ToolContext(task_id="job_smoke", step_index=1, trajectory_id="traj_job_smoke"),
        )
        if not search_result.success or not search_result.result or not search_result.result.get("results"):
            raise RuntimeError(f"Search failed: {search_result.error}")

        first_result = search_result.result["results"][0]

        executor = Executor()
        state = AgentState(
            task_id="job_smoke",
            instruction="Search and review job application page",
            trajectory_id="traj_job_smoke",
        )
        open_result = await executor.execute(
            "open_url",
            {"url": first_result["url"]},
            state,
        )
        if not open_result.success:
            raise RuntimeError(f"Open failed: {open_result.error}")

        read_result = await executor.execute(
            "read_page",
            {},
            state,
        )
        if not read_result.success or not read_result.result:
            raise RuntimeError(f"Read failed: {read_result.error}")

        preview = (read_result.result.get("content") or "")[:400]
        updated = await service.update_application(
            record.application_id,
            ApplicationUpdate(
                status="researching",
                source_url=first_result["url"],
                notes=(
                    "First source reviewed via runtime smoke test.\n\n"
                    f"Snippet: {first_result.get('snippet', '')}\n\n"
                    f"Preview: {preview}"
                ),
                next_action="Compare official job page requirements with candidate profile before filling forms.",
                metadata={
                    "search_provider": search_result.result.get("provider"),
                    "effective_query": search_result.result.get("effective_query"),
                    "page_title": open_result.result.get("title") if open_result.result else None,
                },
            ),
        )
        if updated is None:
            raise RuntimeError("Failed to update application record")

    await close_browser_manager()

    print("=" * 72)
    print("Job Application Smoke Test")
    print("=" * 72)
    print(json.dumps(
        {
            "application_id": updated.application_id,
            "company_name": updated.company_name,
            "role_title": updated.role_title,
            "status": updated.status,
            "source_url": updated.source_url,
            "next_action": updated.next_action,
            "metadata": updated.metadata,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    asyncio.run(main())
