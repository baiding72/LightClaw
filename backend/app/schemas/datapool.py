"""
数据池相关 Schema
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.enums import FailureType, SampleType, TrajectoryType


class DataPoolSampleCreate(BaseModel):
    """创建数据池样本请求"""
    sample_type: SampleType
    trajectory_type: TrajectoryType
    task_id: str
    step_ids: list[str]
    failure_type: Optional[FailureType] = None
    content: dict[str, Any]
    screenshot_paths: Optional[list[str]] = None


class DataPoolSampleResponse(BaseModel):
    """数据池样本响应"""
    sample_id: str
    sample_type: str
    trajectory_type: str
    task_id: str
    step_ids: list[str]
    failure_type: Optional[str] = None
    content: dict[str, Any]
    screenshot_paths: Optional[list[str]] = None
    is_exported: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ToolUseSample(BaseModel):
    """
    Tool-use 训练样本

    用于工具选择和参数填充的微调
    """
    sample_id: str
    instruction: str
    state_summary: str
    available_tools: list[str]
    previous_actions: Optional[list[dict[str, Any]]] = None
    error_feedback: Optional[str] = None
    target_action: str
    target_args: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class SelfCorrectionSample(BaseModel):
    """
    Self-correction 训练样本

    用于错误纠正能力的微调
    """
    sample_id: str
    instruction: str
    state_summary: str
    available_tools: list[str]
    failed_action: str
    failed_args: dict[str, Any]
    error_type: FailureType
    error_message: str
    corrected_action: str
    corrected_args: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class GUIGroundingSample(BaseModel):
    """
    GUI Grounding 训练样本

    用于 GUI 元素定位和动作预测的微调
    """
    sample_id: str
    instruction: str
    screenshot_path: str
    action_type: str  # click, type, select, scroll
    target_element: str  # selector 或描述
    target_description: Optional[str] = None
    bounding_box: Optional[dict[str, float]] = None  # {x, y, width, height}
    action_args: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataPoolFilter(BaseModel):
    """数据池筛选条件"""
    sample_type: Optional[SampleType] = None
    trajectory_type: Optional[TrajectoryType] = None
    failure_type: Optional[FailureType] = None
    is_exported: Optional[bool] = None
    task_id: Optional[str] = None


class DataPoolListResponse(BaseModel):
    """数据池列表响应"""
    samples: list[DataPoolSampleResponse]
    total: int
    page: int
    page_size: int


class DataPoolStats(BaseModel):
    """数据池统计"""
    total_samples: int
    by_type: dict[str, int]
    by_trajectory_type: dict[str, int]
    by_failure_type: dict[str, int]
    exported_count: int
    unexported_count: int


class ExportRequest(BaseModel):
    """导出请求"""
    sample_types: Optional[list[SampleType]] = None
    trajectory_types: Optional[list[TrajectoryType]] = None
    failure_types: Optional[list[FailureType]] = None
    include_exported: bool = False
    output_format: str = "jsonl"  # jsonl, json


class ExportResponse(BaseModel):
    """导出响应"""
    export_id: str
    file_path: str
    total_samples: int
    sample_types: dict[str, int]
    created_at: datetime
