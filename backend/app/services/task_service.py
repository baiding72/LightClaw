"""
任务服务
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TaskCategory, TaskDifficulty, TaskStatus
from app.db.models import TaskModel
from app.scenarios import build_job_application_instruction
from app.schemas.job_application import JobApplicationContext
from app.schemas.task import (
    BrowserContext,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskSummary,
    TaskUpdate,
)


class TaskService:
    """任务服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(self, task_create: TaskCreate) -> TaskResponse:
        """创建任务"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        task = TaskModel(
            task_id=task_id,
            instruction=task_create.instruction,
            category=task_create.category.value,
            difficulty=task_create.difficulty.value,
            allowed_tools=task_create.allowed_tools or [],
            target_state=task_create.target_state,
            validation_rules=task_create.validation_rules,
            browser_context=task_create.browser_context.model_dump(mode="json") if task_create.browser_context else None,
            scenario_type=task_create.scenario_type,
            scenario_context=task_create.scenario_context.model_dump(mode="json") if task_create.scenario_context else None,
            status=TaskStatus.PENDING.value,
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        return self._to_response(task)

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """获取任务"""
        result = await self.db.execute(
            select(TaskModel).where(TaskModel.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return None
        return self._to_response(task)

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> TaskListResponse:
        """获取任务列表"""
        query = select(TaskModel)

        if status:
            query = query.where(TaskModel.status == status)

        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页
        query = query.order_by(TaskModel.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return TaskListResponse(
            tasks=[self._to_summary(t) for t in tasks],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_task(
        self,
        task_id: str,
        task_update: TaskUpdate,
    ) -> Optional[TaskResponse]:
        """更新任务"""
        result = await self.db.execute(
            select(TaskModel).where(TaskModel.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return None

        if task_update.status:
            task.status = task_update.status.value
        if task_update.result:
            task.result = task_update.result
            task.completed_at = datetime.now()

        await self.db.commit()
        await self.db.refresh(task)

        return self._to_response(task)

    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        result = await self.db.execute(
            select(TaskModel).where(TaskModel.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False

        await self.db.delete(task)
        await self.db.commit()
        return True

    async def run_task(
        self,
        task_id: str,
        browser_context: Optional[BrowserContext] = None,
        scenario_context: Optional[JobApplicationContext] = None,
    ) -> dict:
        """运行任务"""
        task = await self.get_task(task_id)
        if not task:
            return {"success": False, "error": "Task not found"}

        # 更新状态为运行中
        await self.update_task(task_id, TaskUpdate(status=TaskStatus.RUNNING))

        try:
            # 运行 Agent
            from app.runtime import Agent
            from app.tasks.definitions import get_task_by_id

            # 获取任务定义
            built_in_task = get_task_by_id(task_id)
            instruction = built_in_task.instruction if built_in_task else task.instruction
            allowed_tools = built_in_task.allowed_tools if built_in_task else task.allowed_tools

            effective_browser_context = browser_context
            if effective_browser_context is None and task.browser_context:
                effective_browser_context = BrowserContext(**task.browser_context)
            effective_scenario_context = scenario_context
            if effective_scenario_context is None and task.scenario_context:
                effective_scenario_context = JobApplicationContext(**task.scenario_context)

            enriched_instruction = instruction
            serialized_browser_context = None
            if effective_browser_context:
                selected_tab = effective_browser_context.selected_tab
                serialized_browser_context = effective_browser_context.model_dump(mode="json")
                other_tabs = [
                    f"- {tab.title or tab.url} ({tab.url})"
                    for tab in effective_browser_context.tabs
                    if tab.tab_id != selected_tab.tab_id
                ][:5]
                browser_lines = [
                    "浏览器插件已提供真实页面上下文，请优先围绕该页面执行任务。",
                    f"当前目标标签页标题: {selected_tab.title or 'Untitled'}",
                    f"当前目标标签页 URL: {selected_tab.url}",
                ]
                if other_tabs:
                    browser_lines.append("同窗口其他标签页:")
                    browser_lines.extend(other_tabs)
                enriched_instruction = f"{instruction}\n\n" + "\n".join(browser_lines)

            serialized_scenario_context = None
            if effective_scenario_context:
                serialized_scenario_context = effective_scenario_context.model_dump(mode="json")
                if task.scenario_type == "job_application":
                    enriched_instruction = build_job_application_instruction(
                        enriched_instruction,
                        serialized_scenario_context,
                    )

            agent = Agent(task_id=task_id)
            result = await agent.run(
                instruction=enriched_instruction,
                allowed_tools=allowed_tools,
                task_definition=built_in_task,
                browser_context=serialized_browser_context,
            )
            if serialized_scenario_context:
                result["scenario_type"] = task.scenario_type
                result["scenario_context"] = serialized_scenario_context

            # 更新任务状态
            status = TaskStatus.COMPLETED if result.get("success") else TaskStatus.FAILED
            await self.update_task(task_id, TaskUpdate(
                status=status,
                result=result,
            ))

            await agent.close()

            return result

        except Exception as e:
            await self.update_task(task_id, TaskUpdate(
                status=TaskStatus.FAILED,
                result={"error": str(e)},
            ))
            return {"success": False, "error": str(e)}

    def _to_response(self, task: TaskModel) -> TaskResponse:
        """转换为响应模型"""
        return TaskResponse(
            task_id=task.task_id,
            instruction=task.instruction,
            category=task.category,
            difficulty=task.difficulty,
            status=task.status,
            allowed_tools=task.allowed_tools or [],
            target_state=task.target_state,
            validation_rules=task.validation_rules,
            browser_context=BrowserContext(**task.browser_context) if task.browser_context else None,
            scenario_type=task.scenario_type,
            scenario_context=JobApplicationContext(**task.scenario_context) if task.scenario_context else None,
            result=task.result,
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at,
        )

    def _to_summary(self, task: TaskModel) -> TaskSummary:
        """转换为摘要模型"""
        return TaskSummary(
            task_id=task.task_id,
            instruction=task.instruction,
            category=task.category,
            difficulty=task.difficulty,
            status=task.status,
            created_at=task.created_at,
        )
