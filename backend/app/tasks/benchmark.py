"""
Benchmark 运行器

运行评测并收集指标
"""
import uuid
from datetime import datetime
from typing import Any

from app.core.enums import TaskCategory, TaskDifficulty
from app.core.logger import logger
from app.runtime import Agent
from app.schemas.eval import EvaluationMetrics, EvaluationResponse, TaskEvaluationDetail
from app.schemas.task import TaskDefinition
from app.tasks.definitions import (
    ALL_TASKS,
)
from app.tasks.validators import MockValidator, TaskValidator


class BenchmarkRunner:
    """Benchmark 运行器"""

    def __init__(self, use_mock_validator: bool = True):
        self.validator = MockValidator() if use_mock_validator else TaskValidator()
        self.results: list[dict[str, Any]] = []

    async def run_single_task(
        self,
        task: TaskDefinition,
        browser_page: Any | None = None,
    ) -> dict[str, Any]:
        """运行单个任务"""
        logger.info(f"Running task: {task.task_id} - {task.instruction[:50]}")

        task_id = f"run_{task.task_id}_{uuid.uuid4().hex[:6]}"

        # 创建 Agent
        agent = Agent(task_id=task_id, browser_page=browser_page)

        try:
            # 执行任务
            result = await agent.run(
                instruction=task.instruction,
                allowed_tools=task.allowed_tools,
                task_definition=task,
            )

            # 验证结果
            validation = self.validator.validate(task, result)

            return {
                "task_id": task.task_id,
                "run_id": task_id,
                "instruction": task.instruction,
                "category": task.category.value,
                "difficulty": task.difficulty.value,
                "is_success": validation.is_success,
                "score": validation.score,
                "steps_count": result.get("total_steps", 0),
                "tool_calls_count": len(result.get("state", {}).get("tool_calls", [])),
                "gui_actions_count": len(result.get("state", {}).get("gui_actions", [])),
                "failure_types": [e.get("type") for e in result.get("errors", [])],
                "recovery_attempts": result.get("retry_count", 0),
                "successful_recoveries": result.get("successful_recoveries", 0),
                "latency_ms": result.get("total_latency_ms", 0),
                "token_usage": result.get("total_tokens", 0),
                "validation": validation.model_dump(),
                "error": result.get("error"),
            }

        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            return {
                "task_id": task.task_id,
                "run_id": task_id,
                "instruction": task.instruction,
                "category": task.category.value,
                "difficulty": task.difficulty.value,
                "is_success": False,
                "score": 0.0,
                "error": str(e),
            }

        finally:
            await agent.close()

    async def run_benchmark(
        self,
        eval_name: str,
        task_ids: list[str] | None = None,
        categories: list[str] | None = None,
        difficulties: list[str] | None = None,
        browser_page: Any | None = None,
    ) -> EvaluationResponse:
        """
        运行 Benchmark

        Args:
            eval_name: 评测名称
            task_ids: 指定任务 ID 列表
            categories: 按类别筛选
            difficulties: 按难度筛选
            browser_page: 浏览器页面

        Returns:
            评测结果
        """
        logger.info(f"Starting benchmark: {eval_name}")

        # 获取要运行的任务
        tasks = self._filter_tasks(task_ids, categories, difficulties)

        if not tasks:
            logger.warning("No tasks to run")
            return EvaluationResponse(
                eval_id=f"eval_{uuid.uuid4().hex[:8]}",
                eval_name=eval_name,
                total_tasks=0,
                metrics=EvaluationMetrics(
                    task_success_rate=0.0,
                    tool_execution_success_rate=0.0,
                    recovery_rate=0.0,
                    gui_action_accuracy=0.0,
                    avg_latency_ms=0.0,
                ),
                details=[],
                created_at=datetime.now(),
            )

        # 运行所有任务
        results = []
        for task in tasks:
            result = await self.run_single_task(task, browser_page)
            results.append(result)
            self.results.append(result)

        # 计算指标
        metrics = self._calculate_metrics(results)

        # 构建详情
        details = [
            TaskEvaluationDetail(
                task_id=r["task_id"],
                instruction=r["instruction"],
                is_success=r["is_success"],
                steps_count=r.get("steps_count", 0),
                tool_calls_count=r.get("tool_calls_count", 0),
                gui_actions_count=r.get("gui_actions_count", 0),
                failure_types=r.get("failure_types", []),
                recovery_attempts=r.get("recovery_attempts", 0),
                successful_recoveries=r.get("successful_recoveries", 0),
                latency_ms=r.get("latency_ms", 0),
                token_usage={"total": r.get("token_usage", 0)},
            )
            for r in results
        ]

        eval_response = EvaluationResponse(
            eval_id=f"eval_{uuid.uuid4().hex[:8]}",
            eval_name=eval_name,
            total_tasks=len(tasks),
            metrics=metrics,
            details=details,
            created_at=datetime.now(),
        )

        logger.info(
            f"Benchmark completed: {eval_name}, "
            f"success rate: {metrics.task_success_rate:.2%}"
        )

        return eval_response

    def _filter_tasks(
        self,
        task_ids: list[str] | None = None,
        categories: list[str] | None = None,
        difficulties: list[str] | None = None,
    ) -> list[TaskDefinition]:
        """筛选任务"""
        if task_ids:
            return [t for t in ALL_TASKS if t.task_id in task_ids]

        tasks = ALL_TASKS

        if categories:
            category_enums = [TaskCategory(c) for c in categories]
            tasks = [t for t in tasks if t.category in category_enums]

        if difficulties:
            difficulty_enums = [TaskDifficulty(d) for d in difficulties]
            tasks = [t for t in tasks if t.difficulty in difficulty_enums]

        return tasks

    def _calculate_metrics(
        self,
        results: list[dict[str, Any]],
    ) -> EvaluationMetrics:
        """计算评测指标"""
        if not results:
            return EvaluationMetrics(
                task_success_rate=0.0,
                tool_execution_success_rate=0.0,
                recovery_rate=0.0,
                gui_action_accuracy=0.0,
                avg_latency_ms=0.0,
            )

        total = len(results)

        # 任务成功率
        successful_tasks = sum(1 for r in results if r.get("is_success"))
        task_success_rate = successful_tasks / total

        # 工具执行成功率：基于当前 run 记录，不使用估计值。
        total_tool_calls = sum(r.get("tool_calls_count", 0) for r in results)
        failed_tool_calls = sum(len(r.get("failure_types", [])) for r in results)
        tool_execution_success_rate = (
            max(0, total_tool_calls - failed_tool_calls) / total_tool_calls
            if total_tool_calls > 0
            else 1.0
        )

        # 恢复率
        total_recovery_attempts = sum(r.get("recovery_attempts", 0) for r in results)
        successful_recoveries = sum(r.get("successful_recoveries", 0) for r in results)
        recovery_rate = (
            successful_recoveries / total_recovery_attempts
            if total_recovery_attempts > 0
            else 1.0
        )

        # GUI 动作准确率：没有 GUI action 时不惩罚。
        total_gui_actions = sum(r.get("gui_actions_count", 0) for r in results)
        gui_failures = sum(
            1
            for r in results
            for failure in r.get("failure_types", [])
            if failure in {"gui_click_miss", "gui_wrong_element", "gui_state_stale"}
        )
        gui_action_accuracy = (
            max(0, total_gui_actions - gui_failures) / total_gui_actions
            if total_gui_actions > 0
            else 1.0
        )

        # 平均延迟
        total_latency = sum(r.get("latency_ms", 0) for r in results)
        avg_latency_ms = total_latency / total if total > 0 else 0.0
        total_steps = sum(r.get("steps_count", 0) for r in results)
        total_failures = max(sum(len(r.get("failure_types", [])) for r in results), 1)
        invalid_tool_calls = sum(
            1 for r in results for failure in r.get("failure_types", []) if failure == "invalid_format"
        )
        wrong_args = sum(
            1 for r in results for failure in r.get("failure_types", []) if failure == "wrong_args"
        )
        policy_violations = sum(
            1 for r in results for failure in r.get("failure_types", []) if failure == "policy_violation"
        )

        return EvaluationMetrics(
            task_success_rate=task_success_rate,
            tool_execution_success_rate=tool_execution_success_rate,
            recovery_rate=recovery_rate,
            gui_action_accuracy=gui_action_accuracy,
            invalid_tool_call_rate=invalid_tool_calls / total_failures,
            wrong_args_rate=wrong_args / total_failures,
            policy_violation_rate=policy_violations / total_failures,
            avg_steps=total_steps / total if total else 0.0,
            avg_latency_ms=avg_latency_ms,
            total_token_cost=0.0,  # TODO: 实际计算
        )

    def get_results_summary(self) -> dict[str, Any]:
        """获取结果摘要"""
        if not self.results:
            return {"total": 0}

        total = len(self.results)
        successful = sum(1 for r in self.results if r.get("is_success"))

        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total,
        }
