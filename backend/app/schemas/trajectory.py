"""
轨迹相关 Schema
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.enums import FailureType, StepStatus


class StepCreate(BaseModel):
    """创建步骤请求"""
    task_id: str
    step_index: int
    thought: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None


class StepResponse(BaseModel):
    """步骤响应"""
    step_id: str
    task_id: str
    step_index: int
    status: str
    thought: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None
    tool_result: Optional[dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    observation: Optional[str] = None
    latency_ms: Optional[int] = None
    token_usage: Optional[dict[str, int]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TrajectoryStep(BaseModel):
    """轨迹步骤（用于日志和数据导出）"""
    step_index: int
    status: StepStatus
    state_summary: Optional[str] = None
    thought: Optional[str] = None
    available_tools: Optional[list[str]] = None
    chosen_tool: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None
    tool_result: Optional[Any] = None
    error_type: Optional[FailureType] = None
    error_message: Optional[str] = None
    observation: Optional[str] = None
    screenshot_path: Optional[str] = None
    target_element: Optional[str] = None
    latency_ms: Optional[int] = None
    token_usage: Optional[dict[str, int]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class Trajectory(BaseModel):
    """
    完整轨迹

    包含一次任务执行的完整信息
    """
    trajectory_id: str
    task_id: str
    user_instruction: str
    category: str
    difficulty: str
    final_outcome: str  # success, failure, partial
    steps: list[TrajectoryStep]
    total_steps: int
    total_latency_ms: int
    total_tokens: int
    failure_types: list[FailureType] = Field(default_factory=list)
    recovery_attempts: int = 0
    successful_recoveries: int = 0
    created_at: datetime = Field(default_factory=datetime.now)

    def to_jsonl(self) -> str:
        """导出为 JSONL 格式"""
        import json
        return json.dumps(self.model_dump(), ensure_ascii=False, default=str)


class TrajectorySummary(BaseModel):
    """轨迹摘要"""
    trajectory_id: str
    task_id: str
    instruction: str
    final_outcome: str
    total_steps: int
    failure_count: int
    recovery_count: int
    created_at: datetime


class TrajectoryListResponse(BaseModel):
    """轨迹列表响应"""
    trajectories: list[TrajectorySummary]
    total: int
    page: int
    page_size: int
