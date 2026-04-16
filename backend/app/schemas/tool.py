"""
工具相关 Schema
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str  # string, integer, number, boolean, array, object
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[list[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class ToolSchema(BaseModel):
    """工具 Schema 定义"""
    name: str
    description: str
    parameters: list[ToolParameter]
    return_type: str
    return_description: str
    examples: list[dict[str, Any]] = Field(default_factory=list)


class ToolCall(BaseModel):
    """工具调用请求"""
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """工具调用结果"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    latency_ms: Optional[int] = None
    screenshot_path: Optional[str] = None


class ToolInfo(BaseModel):
    """工具信息（用于展示）"""
    name: str
    description: str
    category: str
    parameters_summary: str


class ToolRegistryResponse(BaseModel):
    """工具注册表响应"""
    tools: list[ToolInfo]
    total: int
