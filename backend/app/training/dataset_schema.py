"""
训练数据集 Schema 定义
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolUseDatasetSample(BaseModel):
    """
    Tool-use 训练样本

    用于训练模型进行工具选择和参数填充
    """
    id: str
    instruction: str
    state_summary: str
    available_tools: list[str]
    previous_actions: list[dict[str, Any]] = Field(default_factory=list)
    target_action: str
    target_args: dict[str, Any]
    is_positive: bool = True  # 正样本还是负样本
    metadata: dict[str, Any] = Field(default_factory=dict)


class SelfCorrectionDatasetSample(BaseModel):
    """
    Self-correction 训练样本

    用于训练模型的错误纠正能力
    """
    id: str
    instruction: str
    state_summary: str
    available_tools: list[str]
    failed_action: str
    failed_args: dict[str, Any]
    error_type: str
    error_message: str
    corrected_action: str
    corrected_args: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class GUIGroundingDatasetSample(BaseModel):
    """
    GUI Grounding 训练样本

    用于训练模型的 GUI 元素定位能力
    """
    id: str
    instruction: str
    screenshot_path: str
    action_type: str  # click, type, select, scroll
    target_element: str  # selector 或描述
    target_description: Optional[str] = None
    bounding_box: Optional[dict[str, float]] = None  # {x, y, width, height}
    action_args: Optional[dict[str, Any]] = None
    is_success: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(BaseModel):
    """对话消息"""
    role: str  # system, user, assistant
    content: str
    tool_calls: Optional[list[dict[str, Any]]] = None


class ConversationDatasetSample(BaseModel):
    """
    对话格式训练样本

    用于微调模型的对话格式数据
    """
    id: str
    messages: list[ConversationMessage]
    tools: Optional[list[dict[str, Any]]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetStatistics(BaseModel):
    """数据集统计"""
    total_samples: int
    by_type: dict[str, int]
    by_category: dict[str, int]
    avg_instruction_length: float
    avg_action_length: float


class DatasetExportConfig(BaseModel):
    """数据集导出配置"""
    output_format: str = "jsonl"  # jsonl, json, parquet
    include_metadata: bool = True
    include_screenshots: bool = True
    split_ratio: Optional[dict[str, float]] = None  # {"train": 0.8, "val": 0.1, "test": 0.1}
