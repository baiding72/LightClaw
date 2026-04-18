"""
数据库模型定义
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TaskModel(Base):
    """任务模型"""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    instruction: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), index=True)
    difficulty: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    allowed_tools: Mapped[list] = mapped_column(JSON, default=list)
    target_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    validation_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    browser_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    scenario_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    scenario_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class StepModel(Base):
    """步骤模型"""
    __tablename__ = "steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    step_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    thought: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tool_args: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    tool_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    observation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class MemoryModel(Base):
    """记忆模型"""
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    memory_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    memory_type: Mapped[str] = mapped_column(String(16), index=True)
    key: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text)
    memory_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 序列化的向量
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class DataPoolSampleModel(Base):
    """数据池样本模型"""
    __tablename__ = "datapool_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sample_type: Mapped[str] = mapped_column(String(32), index=True)
    trajectory_type: Mapped[str] = mapped_column(String(32), index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    step_ids: Mapped[list] = mapped_column(JSON, default=list)
    failure_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    content: Mapped[dict] = mapped_column(JSON)
    screenshot_paths: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_exported: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class EvaluationResultModel(Base):
    """评测结果模型"""
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    eval_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    eval_name: Mapped[str] = mapped_column(String(128))
    total_tasks: Mapped[int] = mapped_column(Integer)
    task_success_rate: Mapped[float] = mapped_column(Float)
    tool_execution_success_rate: Mapped[float] = mapped_column(Float)
    recovery_rate: Mapped[float] = mapped_column(Float)
    gui_action_accuracy: Mapped[float] = mapped_column(Float)
    avg_latency_ms: Mapped[float] = mapped_column(Float)
    total_token_cost: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class NoteModel(Base):
    """笔记模型（用于本地演示）"""
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class TodoModel(Base):
    """待办模型（用于本地演示）"""
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class CalendarEventModel(Base):
    """日历事件模型（用于本地演示）"""
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    location: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class ApplicationModel(Base):
    """求职申请跟踪模型"""
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(200), index=True)
    role_title: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(32), default="discovered", index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_action: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    application_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
