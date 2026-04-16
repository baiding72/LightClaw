"""
Agent 状态管理
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import json


@dataclass
class AgentState:
    """
    Agent 状态

    跟踪当前任务执行的完整状态
    """

    # 任务信息
    task_id: str
    instruction: str
    trajectory_id: str

    # 当前状态
    current_step: int = 0
    max_steps: int = 20

    # 累计统计
    total_tokens: int = 0
    total_latency_ms: int = 0
    retry_count: int = 0
    successful_recoveries: int = 0

    # 执行历史
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    gui_actions: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    # 短期记忆
    observations: list[str] = field(default_factory=list)
    thoughts: list[str] = field(default_factory=list)

    # 当前上下文
    current_url: Optional[str] = None
    current_page_title: Optional[str] = None
    last_tool_result: Optional[dict[str, Any]] = None
    browser_context: Optional[dict[str, Any]] = None

    # 状态标记
    is_completed: bool = False
    is_failed: bool = False
    final_outcome: Optional[str] = None

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def get_state_summary(self) -> str:
        """获取状态摘要"""
        parts = []

        # 基本信息
        parts.append(f"当前步骤: {self.current_step}/{self.max_steps}")

        # 页面信息
        if self.current_url:
            parts.append(f"当前页面: {self.current_page_title or self.current_url}")
        elif self.browser_context and self.browser_context.get("selected_tab"):
            selected_tab = self.browser_context["selected_tab"]
            parts.append(
                "浏览器目标页面: "
                f"{selected_tab.get('title') or selected_tab.get('url')} "
                f"({selected_tab.get('url')})"
            )

        if self.browser_context and self.browser_context.get("tabs"):
            tabs = self.browser_context["tabs"][:5]
            tab_summaries = [
                f"{tab.get('title') or tab.get('url')} ({tab.get('url')})"
                for tab in tabs
            ]
            parts.append("可用标签页: " + " | ".join(tab_summaries))

        # 最近观察
        if self.observations:
            latest_obs = self.observations[-1]
            parts.append(f"最近观察: {latest_obs[:200]}")

        # 错误信息
        if self.errors:
            parts.append(f"已遇到 {len(self.errors)} 个错误")

        return "\n".join(parts)

    def add_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """记录工具调用"""
        self.tool_calls.append({
            "step": self.current_step,
            "tool": tool_name,
            "args": tool_args,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()

    def add_gui_action(
        self,
        action_type: str,
        target: str,
        success: bool,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """记录 GUI 动作"""
        self.gui_actions.append({
            "step": self.current_step,
            "action": action_type,
            "target": target,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()

    def add_error(
        self,
        error_type: str,
        error_message: str,
        step: Optional[int] = None,
    ) -> None:
        """记录错误"""
        self.errors.append({
            "step": step or self.current_step,
            "type": error_type,
            "message": error_message,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()

    def add_observation(self, observation: str) -> None:
        """添加观察"""
        self.observations.append(observation)
        self.updated_at = datetime.now()

    def add_thought(self, thought: str) -> None:
        """添加思考"""
        self.thoughts.append(thought)
        self.updated_at = datetime.now()

    def increment_step(self) -> None:
        """增加步骤计数"""
        self.current_step += 1
        self.updated_at = datetime.now()

    def add_token_usage(self, tokens: int) -> None:
        """添加 token 使用统计"""
        self.total_tokens += tokens
        self.updated_at = datetime.now()

    def add_latency(self, latency_ms: int) -> None:
        """添加延迟统计"""
        self.total_latency_ms += latency_ms
        self.updated_at = datetime.now()

    def mark_completed(self, outcome: str = "success") -> None:
        """标记任务完成"""
        self.is_completed = True
        self.final_outcome = outcome
        self.updated_at = datetime.now()

    def mark_failed(self, reason: str) -> None:
        """标记任务失败"""
        self.is_failed = True
        self.final_outcome = f"failed: {reason}"
        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "trajectory_id": self.trajectory_id,
            "current_step": self.current_step,
            "max_steps": self.max_steps,
            "total_tokens": self.total_tokens,
            "total_latency_ms": self.total_latency_ms,
            "retry_count": self.retry_count,
            "successful_recoveries": self.successful_recoveries,
            "tool_calls": self.tool_calls,
            "gui_actions": self.gui_actions,
            "errors": self.errors,
            "observations": self.observations,
            "thoughts": self.thoughts,
            "current_url": self.current_url,
            "current_page_title": self.current_page_title,
            "browser_context": self.browser_context,
            "is_completed": self.is_completed,
            "is_failed": self.is_failed,
            "final_outcome": self.final_outcome,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
