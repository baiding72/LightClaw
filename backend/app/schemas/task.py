"""
任务相关 Schema
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.enums import TaskCategory, TaskDifficulty, TaskStatus


class BrowserTabContext(BaseModel):
    """浏览器标签页上下文"""
    tab_id: int
    window_id: int
    title: str
    url: str
    active: bool = False
    fav_icon_url: Optional[str] = None


class BrowserContext(BaseModel):
    """任务运行时的浏览器上下文"""
    source: str = "browser_extension"
    captured_at: datetime
    selected_tab: BrowserTabContext
    tabs: list[BrowserTabContext] = Field(default_factory=list)


class TaskCreate(BaseModel):
    """创建任务请求"""
    instruction: str = Field(..., min_length=1, max_length=2000)
    category: TaskCategory = TaskCategory.MULTI_STEP
    difficulty: TaskDifficulty = TaskDifficulty.MEDIUM
    allowed_tools: Optional[list[str]] = None
    target_state: Optional[dict[str, Any]] = None
    validation_rules: Optional[dict[str, Any]] = None


class TaskUpdate(BaseModel):
    """更新任务请求"""
    status: Optional[TaskStatus] = None
    result: Optional[dict[str, Any]] = None


class TaskRunRequest(BaseModel):
    """运行任务请求"""
    browser_context: Optional[BrowserContext] = None


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    instruction: str
    category: str
    difficulty: str
    status: str
    allowed_tools: list[str]
    target_state: Optional[dict[str, Any]] = None
    validation_rules: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskSummary(BaseModel):
    """任务摘要"""
    task_id: str
    instruction: str
    category: str
    difficulty: str
    status: str
    created_at: datetime


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: list[TaskSummary]
    total: int
    page: int
    page_size: int


class TaskDefinition(BaseModel):
    """
    任务定义（用于内置任务集）

    每个任务包含：
    - instruction: 用户指令
    - category: 任务类别
    - difficulty: 难度级别
    - allowed_tools: 允许使用的工具列表
    - target_state: 目标状态描述
    - validation_rules: 自动验证规则
    - initial_state: 初始状态（可选）
    """
    task_id: str
    instruction: str
    category: TaskCategory
    difficulty: TaskDifficulty
    allowed_tools: list[str]
    target_state: dict[str, Any]
    validation_rules: dict[str, Any]
    initial_state: Optional[dict[str, Any]] = None
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class TaskValidationResult(BaseModel):
    """任务验证结果"""
    is_success: bool
    score: float = Field(..., ge=0.0, le=1.0)
    checks: list[dict[str, Any]]
    error_message: Optional[str] = None
