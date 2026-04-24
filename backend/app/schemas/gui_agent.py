"""
GUI Agent 结构化 Schema
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


ActionSpace = Literal["CLICK", "TYPE", "SCROLL", "WAIT", "FINISH"]
ScrollDirection = Literal["up", "down"]
TaskStrategy = Literal["read", "write"]


class ViewportMetadata(BaseModel):
    url: str = Field(..., description="当前页面 URL")
    title: str = Field(..., description="当前页面标题")
    viewport_width: int = Field(..., ge=0)
    viewport_height: int = Field(..., ge=0)
    scroll_x: int = Field(..., ge=0)
    scroll_y: int = Field(..., ge=0)
    timestamp: str = Field(..., description="观测时间戳")


class InteractiveElementObservation(BaseModel):
    agent_id: str = Field(..., description="插件注入的全局唯一元素 ID")
    tag: str = Field(..., description="DOM 标签名")
    role: str = Field(..., description="交互角色")
    text: str = Field(default="", description="元素可见文本")
    aria_label: Optional[str] = Field(default=None, description="ARIA 标签")
    placeholder: Optional[str] = Field(default=None, description="输入提示文本")
    href: Optional[str] = Field(default=None, description="链接地址")
    value: Optional[str] = Field(default=None, description="当前值")
    disabled: bool = Field(..., description="元素是否禁用")
    checked: Optional[bool] = Field(default=None, description="checkbox/radio 选中状态")
    context_text: Optional[str] = Field(default=None, description="元素周围上下文文本")
    rect: dict = Field(..., description="元素在视口中的矩形框")


class Observation(BaseModel):
    metadata: ViewportMetadata
    nodes: list[InteractiveElementObservation] = Field(default_factory=list)
    som_text: str = Field(..., description="Set-of-Mark 风格的紧凑文本观察")
    screenshot_base64: Optional[str] = Field(default=None, description="当前视口的 SoM 标注截图（Base64 data URL）")
    previous_error_trace: Optional[str] = Field(
        default=None,
        description="上一步动作失败后的错误回流，用于自纠错",
    )


class GuiDecisionRequest(BaseModel):
    task_description: str = Field(..., min_length=1, description="用户任务描述")
    observation: Observation
    previous_error_trace: Optional[str] = Field(default=None, description="前端保存的上一轮错误信息")
    task_id: Optional[str] = Field(default=None, description="前端任务 ID，用于轨迹聚合")
    step_index: Optional[int] = Field(default=1, ge=1, description="当前循环步数")


class ReadExtractionRecord(BaseModel):
    job_name: Optional[str] = None
    status: Optional[str] = None
    delivery_time: Optional[str] = None
    evidence: Optional[str] = None


class ReadTaskExtraction(BaseModel):
    thought_process: str = Field(..., min_length=1, max_length=240)
    records: list[ReadExtractionRecord] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    needs_more_context: bool = Field(default=False)
    suggested_next_action: Optional[ActionSpace] = Field(default=None)
    target_id: Optional[str] = Field(default=None)
    action_value: Optional[str | int] = Field(default=None)

    @model_validator(mode="after")
    def validate_read_extraction(self) -> "ReadTaskExtraction":
        self.thought_process = self.thought_process.strip()[:240]
        if isinstance(self.action_value, int):
            self.action_value = str(self.action_value)
        elif isinstance(self.action_value, str):
            self.action_value = self.action_value.strip() or None

        normalized_records = []
        for record in self.records:
            normalized_records.append(
                ReadExtractionRecord(
                    job_name=(record.job_name or "").strip() or None,
                    status=(record.status or "").strip() or None,
                    delivery_time=(record.delivery_time or "").strip() or None,
                    evidence=(record.evidence or "").strip() or None,
                )
            )
        self.records = normalized_records

        normalized_missing_fields = []
        for field in self.missing_fields:
            text = str(field or "").strip()
            if text:
                normalized_missing_fields.append(text[:80])
        self.missing_fields = normalized_missing_fields[:8]

        effective_action = self.suggested_next_action or ("SCROLL" if self.needs_more_context else "FINISH")
        if effective_action != "FINISH":
            return self

        if not self.records:
            raise ValueError(
                "ValidationError: 提取失败。你输出了 FINISH，但 records 是空的。请严格对照观察到的 [TEXT] 节点真实内容填充字段；如果首屏不完整，请执行 SCROLL 继续寻找。"
            )

        for index, record in enumerate(self.records, start=1):
            if not record.job_name and not record.status:
                raise ValueError(
                    f"ValidationError: 提取失败。你输出了 FINISH，但 records 第 {index} 条是空数据：job_name 和 status 都是 null/空字符串。请严格对照观察到的 [TEXT] 节点真实内容填充字段；如果确实还没有足够数据，请执行 SCROLL 动作继续寻找。"
                )

        return self


class AgentDecision(BaseModel):
    thought_process: str = Field(
        ...,
        description="简洁、可审计的决策理由。必须结合 Observation 说明为什么选择这个动作。",
        min_length=1,
    )
    action_type: ActionSpace = Field(..., description="下一步动作类型")
    target_id: Optional[str] = Field(
        default=None,
        description="目标元素的 agent_id。CLICK/TYPE 时必须提供。",
    )
    action_value: Optional[str] = Field(
        default=None,
        description="TYPE 时为输入文本；SCROLL 时为 up/down；WAIT 时为毫秒数字符串；FINISH 时可为空。",
    )
    strategy: Optional[TaskStrategy] = Field(
        default=None,
        description="决策采用的子策略：read 或 write。",
    )
    structured_output: Optional[dict[str, Any]] = Field(
        default=None,
        description="读任务提取出的结构化结果。",
    )

    @model_validator(mode="after")
    def validate_action_payload(self) -> "AgentDecision":
        if self.action_type == "SCROLL" and self.action_value:
            self.action_value = self.action_value.lower()

        if self.action_type in {"CLICK", "TYPE"} and not self.target_id:
            raise ValueError(f"{self.action_type} 动作必须提供 target_id")

        if self.action_type == "TYPE" and not self.action_value:
            raise ValueError("TYPE 动作必须提供 action_value")

        if self.action_type == "SCROLL":
            if self.action_value not in {"up", "down"}:
                raise ValueError("SCROLL 动作的 action_value 必须是 up 或 down")
            if self.target_id is not None:
                raise ValueError("SCROLL 动作不应提供 target_id")

        if self.action_type == "WAIT":
            if not self.action_value:
                raise ValueError("WAIT 动作必须提供等待毫秒数")
            try:
                wait_ms = int(self.action_value)
            except ValueError as exc:
                raise ValueError("WAIT 动作的 action_value 必须是毫秒数字符串") from exc
            if wait_ms <= 0:
                raise ValueError("WAIT 动作的等待时长必须大于 0")
            if self.target_id is not None:
                raise ValueError("WAIT 动作不应提供 target_id")

        if self.action_type == "FINISH":
            if self.target_id is not None:
                raise ValueError("FINISH 动作不应提供 target_id")

        return self


class ActionExecutionResult(BaseModel):
    success: bool = Field(..., description="动作执行是否成功")
    status: Literal["Success", "ElementNotFound", "Error"] = Field(..., description="执行状态")
    action_type: ActionSpace = Field(..., description="已执行动作类型")
    target_id: Optional[str] = Field(default=None, description="目标元素 ID")
    detail: Optional[str] = Field(default=None, description="补充说明")
    error: Optional[str] = Field(default=None, description="失败错误信息")


class AgentLoopResult(BaseModel):
    success: bool
    summary: str
    total_steps: int
    retry_count: int = 0
    final_observation: Optional[Observation] = None
    last_decision: Optional[AgentDecision] = None
    last_execution_result: Optional[ActionExecutionResult] = None


class GuiTraceRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    step_index: int = Field(..., ge=1)
    task_description: Optional[str] = Field(default=None)
    observation: Optional[Observation] = None
    decision: Optional[AgentDecision] = None
    execution_result: Optional[ActionExecutionResult] = None
    previous_error_trace: Optional[str] = None
    rejected_decision: Optional[AgentDecision] = Field(
        default=None,
        description="失败轨迹中的错误决策，可用于构建 rejected 样本",
    )
