"""
Agent 主循环

实现 MiniClaw 风格的轻量 Agent Runtime
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from app.core.config import get_settings
from app.core.enums import TaskStatus
from app.core.logger import logger
from app.gateway.collector import GatewayCollector
from app.llm import get_llm_adapter
from app.memory.manager import MemoryManager
from app.runtime.executor import Executor
from app.runtime.observer import Observer
from app.runtime.planner import Planner
from app.runtime.retry import RecoveryManager
from app.runtime.state import AgentState
from app.schemas.task import TaskDefinition
from app.schemas.trajectory import Trajectory, TrajectoryStep
from app.tools import get_tool_registry


class Agent:
    """
    MiniClaw 风格 Agent

    核心循环：Plan -> Act -> Observe -> Retry/Replan
    """

    def __init__(
        self,
        task_id: Optional[str] = None,
        browser_page: Optional[Any] = None,
    ):
        self.settings = get_settings()
        self.task_id = task_id or str(uuid.uuid4())[:8]
        self.browser_page = browser_page

        # 初始化组件
        self.planner = Planner()
        self.executor = Executor()
        self.observer = Observer()
        self.recovery = RecoveryManager()
        self.memory = MemoryManager()
        self.gateway = GatewayCollector()

        # 状态
        self.state: Optional[AgentState] = None

    async def run(
        self,
        instruction: str,
        allowed_tools: Optional[list[str]] = None,
        task_definition: Optional[TaskDefinition] = None,
        browser_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        运行 Agent 执行任务

        这是核心入口方法

        Args:
            instruction: 用户指令
            allowed_tools: 允许使用的工具列表
            task_definition: 任务定义（可选，用于验证）

        Returns:
            执行结果
        """
        # 初始化状态
        trajectory_id = f"traj_{self.task_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.state = AgentState(
            task_id=self.task_id,
            instruction=instruction,
            trajectory_id=trajectory_id,
            max_steps=self.settings.max_steps,
            browser_context=browser_context,
        )

        logger.info(f"Starting agent run: {self.task_id}, instruction: {instruction[:100]}")

        # 获取可用工具
        tool_registry = get_tool_registry()
        if allowed_tools:
            tools = [t for t in tool_registry.get_schemas() if t["name"] in allowed_tools]
        else:
            tools = tool_registry.get_schemas()
            allowed_tools = [t["name"] for t in tools]

        # 开始事件
        await self.gateway.log_task_start(
            task_id=self.task_id,
            instruction=instruction,
            allowed_tools=allowed_tools,
        )

        try:
            # 初始规划
            plan = await self.planner.plan(instruction, self.state, allowed_tools)
            logger.info(f"Initial plan: {plan}")

            # 主循环
            while True:
                # 检查是否应该继续
                should_continue, reason = self.observer.should_continue(self.state)
                if not should_continue:
                    logger.info(f"Stopping: {reason}")
                    break

                # 增加步骤
                self.state.increment_step()

                # 决定下一步动作
                decision = await self.planner.decide_next_action(self.state, allowed_tools)

                # 记录思考
                if decision.get("thought"):
                    self.state.add_thought(decision["thought"])

                # 如果没有工具调用，可能是完成了
                if not decision.get("tool_name"):
                    # 检查是否是完成响应
                    response = decision.get("response", "")
                    if self._is_completion_response(response):
                        self.state.mark_completed("success")
                        break
                    # 否则继续
                    continue

                # 执行工具
                tool_name = decision["tool_name"]
                tool_args = decision["tool_args"]

                # 记录步骤开始
                step_id = await self.gateway.log_step_start(
                    task_id=self.task_id,
                    step_index=self.state.current_step,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    state_summary=self.state.get_state_summary(),
                    available_tools=allowed_tools,
                )

                # 执行（带重试）
                result = await self.executor.execute_with_retry(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    state=self.state,
                    max_retries=self.settings.max_retries,
                    browser_page=self.browser_page,
                    screenshot_dir=self.settings.screenshots_dir,
                )

                # 观察结果
                observation = await self.observer.observe(tool_name, result, self.state)

                # 记录步骤结束
                await self.gateway.log_step_end(
                    step_id=step_id,
                    result=result,
                    observation=observation,
                    error_type=result.error_type,
                )

                # 处理失败
                if not result.success:
                    # 分析失败
                    analysis = await self.recovery.analyze_failure(
                        tool_name, tool_args, result, self.state
                    )

                    # 尝试恢复
                    if analysis.get("is_recoverable"):
                        recovery_plan = await self.recovery.generate_recovery_plan(
                            self.state, analysis
                        )
                        if recovery_plan:
                            logger.info(f"Attempting recovery: {recovery_plan}")

                # 检查任务完成
                completion = self.observer.check_task_completion(self.state, result)
                if completion:
                    self.state.mark_completed(completion)
                    break

            # 构建最终结果
            final_result = self._build_final_result()

            # 记录任务结束
            await self.gateway.log_task_end(
                task_id=self.task_id,
                final_outcome=self.state.final_outcome or "unknown",
                total_steps=self.state.current_step,
                total_tokens=self.state.total_tokens,
            )

            return final_result

        except Exception as e:
            logger.error(f"Agent run error: {e}")
            self.state.mark_failed(str(e))

            await self.gateway.log_task_end(
                task_id=self.task_id,
                final_outcome="error",
                error_message=str(e),
            )

            return {
                "success": False,
                "error": str(e),
                "state": self.state.to_dict() if self.state else None,
            }

    def _is_completion_response(self, response: str) -> bool:
        """判断是否是完成响应"""
        completion_indicators = [
            "任务已完成",
            "任务完成",
            "已完成",
            "完成",
            "finished",
            "completed",
        ]
        response_lower = response.lower()
        return any(indicator in response_lower for indicator in completion_indicators)

    def _build_final_result(self) -> dict[str, Any]:
        """构建最终结果"""
        return {
            "success": self.state.is_completed and not self.state.is_failed,
            "task_id": self.task_id,
            "trajectory_id": self.state.trajectory_id,
            "instruction": self.state.instruction,
            "outcome": self.state.final_outcome,
            "total_steps": self.state.current_step,
            "total_tokens": self.state.total_tokens,
            "total_latency_ms": self.state.total_latency_ms,
            "retry_count": self.state.retry_count,
            "successful_recoveries": self.state.successful_recoveries,
            "errors": self.state.errors,
            "state": self.state.to_dict(),
        }

    def get_trajectory(self) -> Optional[Trajectory]:
        """获取轨迹"""
        if not self.state:
            return None

        steps = []
        for i, tool_call in enumerate(self.state.tool_calls):
            step = TrajectoryStep(
                step_index=i + 1,
                status="success" if not tool_call.get("error") else "failed",
                thought=self.state.thoughts[i] if i < len(self.state.thoughts) else None,
                chosen_tool=tool_call.get("tool"),
                tool_args=tool_call.get("args"),
                tool_result=tool_call.get("result"),
                error_message=tool_call.get("error"),
                latency_ms=0,  # TODO: 记录实际延迟
            )
            steps.append(step)

        return Trajectory(
            trajectory_id=self.state.trajectory_id,
            task_id=self.task_id,
            user_instruction=self.state.instruction,
            category="unknown",  # TODO: 从任务定义获取
            difficulty="medium",
            final_outcome=self.state.final_outcome or "unknown",
            steps=steps,
            total_steps=len(steps),
            total_latency_ms=self.state.total_latency_ms,
            total_tokens=self.state.total_tokens,
            failure_types=[e["type"] for e in self.state.errors],
            recovery_attempts=self.state.retry_count,
            successful_recoveries=self.state.successful_recoveries,
        )

    async def close(self) -> None:
        """清理资源"""
        # 关闭 LLM 客户端
        llm = get_llm_adapter()
        if hasattr(llm, "close"):
            await llm.close()
