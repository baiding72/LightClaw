"""
Gateway 收集器

统一收集和记录运行时事件
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logger import logger
from app.gateway.event_schema import ErrorEvent, StepEvent, TaskEvent
from app.schemas.tool import ToolResult


class GatewayCollector:
    """
    Gateway 收集器

    负责收集、处理和持久化运行时事件
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.settings = get_settings()
        self.output_dir = Path(output_dir or self.settings.trajectories_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 内存缓存
        self.events: list[dict[str, Any]] = []
        self.current_task_id: Optional[str] = None
        self.current_trajectory: list[dict[str, Any]] = []

    async def log_task_start(
        self,
        task_id: str,
        instruction: str,
        allowed_tools: list[str],
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        target_state: Optional[dict[str, Any]] = None,
        browser_context: Optional[dict[str, Any]] = None,
    ) -> str:
        """记录任务开始"""
        event_id = str(uuid.uuid4())

        event = TaskEvent(
            event_id=event_id,
            task_id=task_id,
            user_instruction=instruction,
            category=category,
            difficulty=difficulty,
            allowed_tools=allowed_tools,
            target_state=target_state,
            browser_context=browser_context,
        )

        self.current_task_id = task_id
        self.current_trajectory = []

        await self._record_event(event.to_dict())
        logger.info(f"Task started: {task_id}")

        return event_id

    async def log_step_start(
        self,
        task_id: str,
        step_index: int,
        tool_name: str,
        tool_args: dict[str, Any],
        state_summary: str,
        available_tools: list[str],
        thought: Optional[str] = None,
    ) -> str:
        """记录步骤开始"""
        event_id = f"step_{task_id}_{step_index}"

        event = StepEvent(
            event_id=event_id,
            task_id=task_id,
            trajectory_id=f"traj_{task_id}",
            step_index=step_index,
            state_summary=state_summary,
            available_tools=available_tools,
            chosen_tool=tool_name,
            tool_args=tool_args,
            thought=thought,
        )

        await self._record_event(event.to_dict())

        return event_id

    async def log_step_end(
        self,
        step_id: str,
        result: ToolResult,
        observation: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> None:
        """记录步骤结束"""
        # 更新事件
        update_data = {
            "tool_result": result.result if result.success else None,
            "error_type": error_type or result.error_type,
            "error_message": result.error,
            "observation": observation,
            "latency_ms": result.latency_ms,
            "screenshot_path": result.screenshot_path,
        }

        # 找到对应的步骤事件并更新
        for event in reversed(self.current_trajectory):
            if event.get("event_id") == step_id:
                event.update(update_data)
                break

        # 记录错误事件
        if not result.success and result.error:
            await self.log_error(
                task_id=self.current_task_id or "",
                step_index=0,  # 从 step_id 提取
                error_type=error_type or result.error_type or "unknown",
                error_message=result.error,
                tool_name=None,  # 从步骤获取
            )

    async def log_task_end(
        self,
        task_id: str,
        final_outcome: str,
        total_steps: int = 0,
        total_tokens: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """记录任务结束"""
        event_id = str(uuid.uuid4())

        event = TaskEvent(
            event_id=event_id,
            task_id=task_id,
            final_outcome=final_outcome,
            total_steps=total_steps,
            total_tokens=total_tokens,
            error_message=error_message,
        )

        await self._record_event(event.to_dict())

        # 持久化轨迹
        await self._persist_trajectory(task_id)

        logger.info(f"Task ended: {task_id}, outcome: {final_outcome}")

        self.current_task_id = None

    async def log_error(
        self,
        task_id: str,
        step_index: int,
        error_type: str,
        error_message: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[dict[str, Any]] = None,
    ) -> str:
        """记录错误"""
        event_id = str(uuid.uuid4())

        event = ErrorEvent(
            event_id=event_id,
            task_id=task_id,
            step_index=step_index,
            error_type=error_type,
            error_message=error_message,
            tool_name=tool_name,
            tool_args=tool_args,
        )

        await self._record_event(event.to_dict())
        logger.warning(f"Error logged: {error_type} - {error_message}")

        return event_id

    async def log_gui_action(
        self,
        task_id: str,
        step_index: int,
        action_type: str,
        target_element: str,
        screenshot_path: Optional[str] = None,
        success: bool = True,
    ) -> None:
        """记录 GUI 动作"""
        event = StepEvent(
            event_id=f"gui_{task_id}_{step_index}",
            task_id=task_id,
            step_index=step_index,
            gui_action_type=action_type,
            target_element=target_element,
            screenshot_path=screenshot_path,
        )

        await self._record_event(event.to_dict())

    async def _record_event(self, event: dict[str, Any]) -> None:
        """记录事件"""
        self.events.append(event)

        if self.current_task_id:
            self.current_trajectory.append(event)

    async def _persist_trajectory(self, task_id: str) -> None:
        """持久化轨迹到文件"""
        if not self.current_trajectory:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trajectory_{task_id}_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                for event in self.current_trajectory:
                    f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

            logger.info(f"Trajectory saved: {filepath}")

        except Exception as e:
            logger.error(f"Failed to persist trajectory: {e}")

    def get_events(self, task_id: Optional[str] = None) -> list[dict[str, Any]]:
        """获取事件列表"""
        if task_id:
            return [e for e in self.events if e.get("task_id") == task_id]
        return self.events.copy()

    def get_trajectory(self, task_id: str) -> list[dict[str, Any]]:
        """获取任务轨迹"""
        return [e for e in self.events if e.get("task_id") == task_id]
