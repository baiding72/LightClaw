"""
Gateway 事件 Schema

定义日志事件的格式
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class StepEvent:
    """
    步骤事件

    记录单个执行步骤的完整信息
    """
    # 基本信息
    event_type: str = "step"
    event_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # 任务上下文
    task_id: str = ""
    trajectory_id: str = ""
    step_index: int = 0

    # 状态
    state_summary: str = ""

    # 工具信息
    available_tools: list[str] = field(default_factory=list)
    chosen_tool: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None

    # 执行结果
    tool_result: Optional[dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # 观察
    observation: Optional[str] = None
    thought: Optional[str] = None

    # GUI 相关
    screenshot_path: Optional[str] = None
    target_element: Optional[str] = None
    gui_action_type: Optional[str] = None

    # 性能指标
    latency_ms: int = 0
    token_usage: Optional[dict[str, int]] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "trajectory_id": self.trajectory_id,
            "step_index": self.step_index,
            "state_summary": self.state_summary,
            "available_tools": self.available_tools,
            "chosen_tool": self.chosen_tool,
            "tool_args": self.tool_args,
            "tool_result": self.tool_result,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "observation": self.observation,
            "thought": self.thought,
            "screenshot_path": self.screenshot_path,
            "target_element": self.target_element,
            "gui_action_type": self.gui_action_type,
            "latency_ms": self.latency_ms,
            "token_usage": self.token_usage,
        }


@dataclass
class TaskEvent:
    """
    任务事件

    记录任务开始和结束
    """
    # 基本信息
    event_type: str = "task"
    event_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # 任务信息
    task_id: str = ""
    user_instruction: str = ""
    category: Optional[str] = None
    difficulty: Optional[str] = None
    allowed_tools: list[str] = field(default_factory=list)
    target_state: Optional[dict[str, Any]] = None
    browser_context: Optional[dict[str, Any]] = None

    # 结果
    final_outcome: Optional[str] = None
    total_steps: int = 0
    total_tokens: int = 0
    total_latency_ms: int = 0
    error_message: Optional[str] = None

    # 统计
    failure_types: list[str] = field(default_factory=list)
    recovery_attempts: int = 0
    successful_recoveries: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "user_instruction": self.user_instruction,
            "category": self.category,
            "difficulty": self.difficulty,
            "allowed_tools": self.allowed_tools,
            "target_state": self.target_state,
            "browser_context": self.browser_context,
            "final_outcome": self.final_outcome,
            "total_steps": self.total_steps,
            "total_tokens": self.total_tokens,
            "total_latency_ms": self.total_latency_ms,
            "error_message": self.error_message,
            "failure_types": self.failure_types,
            "recovery_attempts": self.recovery_attempts,
            "successful_recoveries": self.successful_recoveries,
        }


@dataclass
class ErrorEvent:
    """
    错误事件

    记录错误详情
    """
    # 基本信息
    event_type: str = "error"
    event_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # 上下文
    task_id: str = ""
    step_index: int = 0

    # 错误信息
    error_type: str = ""
    error_message: str = ""
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None

    # 修复信息
    recovery_attempted: bool = False
    recovery_success: bool = False
    recovery_strategy: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "step_index": self.step_index,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "recovery_attempted": self.recovery_attempted,
            "recovery_success": self.recovery_success,
            "recovery_strategy": self.recovery_strategy,
        }
