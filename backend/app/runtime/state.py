"""
Agent 状态管理
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return datetime.now()


@dataclass
class AgentState:
    """
    Agent 状态

    跟踪当前任务执行的完整状态，并作为前台 Agent Run View 的数据源。
    """

    task_id: str
    instruction: str
    trajectory_id: str

    current_step: int = 0
    max_steps: int = 20

    total_tokens: int = 0
    total_latency_ms: int = 0
    retry_count: int = 0
    successful_recoveries: int = 0

    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    gui_actions: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    observations: list[str] = field(default_factory=list)
    thoughts: list[str] = field(default_factory=list)

    current_url: Optional[str] = None
    current_page_title: Optional[str] = None
    current_page_source: Optional[dict[str, Any]] = None
    current_site_profile: Optional[dict[str, Any]] = None
    last_tool_result: Optional[dict[str, Any]] = None
    browser_context: Optional[dict[str, Any]] = None
    scenario_type: Optional[str] = None
    scenario_context: Optional[dict[str, Any]] = None
    browser_runtime_initialized: bool = False

    current_goal: Optional[str] = None
    current_subgoal: Optional[str] = None
    plan_steps: list[str] = field(default_factory=list)
    expected_result: Optional[str] = None
    lifecycle_status: str = "planning"

    candidate_tools: list[dict[str, Any]] = field(default_factory=list)
    current_decision: Optional[dict[str, Any]] = None
    decision_trace: list[dict[str, Any]] = field(default_factory=list)
    recovery_trace: list[dict[str, Any]] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    active_checkpoint: Optional[dict[str, Any]] = None

    memory_summary: dict[str, Any] = field(default_factory=dict)

    is_completed: bool = False
    is_failed: bool = False
    final_outcome: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def refresh_memory_summary(self) -> None:
        selected_tab = self.browser_context.get("selected_tab") if self.browser_context else None
        page_content = (self.browser_context or {}).get("page_content")
        self.memory_summary = {
            "goal": self.current_goal or self.instruction,
            "subgoal": self.current_subgoal,
            "scenario_type": self.scenario_type,
            "selected_tab": {
                "title": selected_tab.get("title"),
                "url": selected_tab.get("url"),
            } if selected_tab else None,
            "browser_page_content": {
                "available": bool(page_content),
                "length": len(str(page_content or "")),
                "format": (self.browser_context or {}).get("content_format"),
                "strategy": (self.browser_context or {}).get("extraction_strategy"),
            } if self.browser_context else None,
            "current_page": {
                "title": self.current_page_title,
                "url": self.current_url,
                "source": self.current_page_source,
                "site_profile": self.current_site_profile,
            } if self.current_url or self.current_page_title else None,
            "expected_result": self.expected_result,
            "last_observation": self.observations[-1] if self.observations else None,
            "last_tool": self.tool_calls[-1]["tool"] if self.tool_calls else None,
            "active_checkpoint": {
                "type": self.active_checkpoint.get("type"),
                "title": self.active_checkpoint.get("title"),
                "resume_hint": self.active_checkpoint.get("resume_hint"),
            } if self.active_checkpoint else None,
            "checkpoint_count": len(self.checkpoints),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }

    def get_environment_snapshot(self) -> dict[str, Any]:
        selected_tab = self.browser_context.get("selected_tab") if self.browser_context else None
        tabs = self.browser_context.get("tabs", [])[:5] if self.browser_context else []
        return {
            "current_url": self.current_url,
            "current_page_title": self.current_page_title,
            "current_page_source": self.current_page_source,
            "current_site_profile": self.current_site_profile,
            "selected_tab": selected_tab,
            "tabs": tabs,
            "page_content_available": bool((self.browser_context or {}).get("page_content")),
            "page_content_length": len(str((self.browser_context or {}).get("page_content", "") or "")),
            "scenario_type": self.scenario_type,
            "scenario_context": self.scenario_context,
        }

    def get_state_summary(self) -> str:
        parts = [
            f"生命周期: {self.lifecycle_status}",
            f"当前步骤: {self.current_step}/{self.max_steps}",
        ]

        if self.current_goal:
            parts.append(f"当前 Goal: {self.current_goal}")
        if self.current_subgoal:
            parts.append(f"当前 Subgoal: {self.current_subgoal}")

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
            tab_summaries = [
                f"{tab.get('title') or tab.get('url')} ({tab.get('url')})"
                for tab in self.browser_context["tabs"][:5]
            ]
            parts.append("可用标签页: " + " | ".join(tab_summaries))

        if self.browser_context and self.browser_context.get("page_content"):
            parts.append(
                "浏览器已提取当前页正文: "
                f"{len(str(self.browser_context.get('page_content') or ''))} 字符"
            )

        if self.current_page_source:
            source_name = self.current_page_source.get("source") or self.current_page_source.get("provider")
            source_query = self.current_page_source.get("search_query")
            if source_name:
                parts.append(f"页面来源: {source_name}")
            if source_query:
                parts.append(f"搜索查询: {source_query}")

        if self.active_checkpoint:
            parts.append(
                f"等待用户处理 Checkpoint: {self.active_checkpoint.get('title') or self.active_checkpoint.get('type')}"
            )

        if self.observations:
            parts.append(f"最近 Observation: {self.observations[-1][:200]}")

        if self.errors:
            parts.append(f"已遇到 {len(self.errors)} 个错误")

        return "\n".join(parts)

    def set_plan(self, understanding: str, steps: list[str], expected_result: str) -> None:
        self.current_goal = understanding or self.instruction
        self.plan_steps = steps
        self.expected_result = expected_result
        if steps:
            self.current_subgoal = steps[min(self.current_step, len(steps) - 1)]
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def set_lifecycle(self, lifecycle_status: str) -> None:
        self.lifecycle_status = lifecycle_status
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def advance_subgoal(self) -> None:
        if not self.plan_steps:
            return
        next_index = min(len(self.tool_calls), len(self.plan_steps) - 1)
        self.current_subgoal = self.plan_steps[next_index]
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def set_candidate_tools(self, candidate_tools: list[dict[str, Any]]) -> None:
        self.candidate_tools = candidate_tools
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def record_decision(
        self,
        *,
        candidate_tools: list[dict[str, Any]],
        chosen_tool: Optional[str],
        chosen_tool_reason: str,
        tool_args: Optional[dict[str, Any]] = None,
        response: Optional[str] = None,
    ) -> None:
        self.candidate_tools = candidate_tools
        self.current_decision = {
            "step": self.current_step,
            "candidate_tools": candidate_tools,
            "chosen_tool": chosen_tool,
            "chosen_tool_reason": chosen_tool_reason,
            "tool_args": tool_args,
            "response": response,
            "timestamp": datetime.now().isoformat(),
        }
        self.decision_trace.append(self.current_decision)
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def record_recovery(
        self,
        *,
        tool_name: str,
        error_type: str,
        error_message: str,
        suggested_action: Optional[str] = None,
        suggested_fix: Optional[Any] = None,
        recovery_plan: Optional[dict[str, Any]] = None,
    ) -> None:
        self.recovery_trace.append({
            "step": self.current_step,
            "tool_name": tool_name,
            "error_type": error_type,
            "error_message": error_message,
            "suggested_action": suggested_action,
            "suggested_fix": suggested_fix,
            "recovery_plan": recovery_plan,
            "timestamp": datetime.now().isoformat(),
        })
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_checkpoint(
        self,
        *,
        checkpoint_type: str,
        title: str,
        description: str,
        resume_hint: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        checkpoint = {
            "id": f"ckpt_{self.task_id}_{len(self.checkpoints) + 1}",
            "step": self.current_step,
            "type": checkpoint_type,
            "title": title,
            "description": description,
            "resume_hint": resume_hint,
            "status": "pending",
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }
        self.checkpoints.append(checkpoint)
        self.active_checkpoint = checkpoint
        self.lifecycle_status = "waiting_for_user"
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def resume_from_checkpoint(self) -> None:
        if self.active_checkpoint:
            self.active_checkpoint["status"] = "completed"
            self.active_checkpoint["completed_at"] = datetime.now().isoformat()
        self.active_checkpoint = None
        self.lifecycle_status = "running"
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        self.tool_calls.append({
            "step": self.current_step,
            "tool": tool_name,
            "args": tool_args,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_action(self, action: dict[str, Any]) -> None:
        self.actions.append(action)
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_gui_action(
        self,
        action_type: str,
        target: str,
        success: bool,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.gui_actions.append({
            "step": self.current_step,
            "action": action_type,
            "target": target,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        })
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_error(
        self,
        error_type: str,
        error_message: str,
        step: Optional[int] = None,
    ) -> None:
        self.errors.append({
            "step": step or self.current_step,
            "type": error_type,
            "message": error_message,
            "timestamp": datetime.now().isoformat(),
        })
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_warning(
        self,
        warning_type: str,
        warning_message: str,
        step: Optional[int] = None,
    ) -> None:
        self.warnings.append({
            "step": step or self.current_step,
            "type": warning_type,
            "message": warning_message,
            "timestamp": datetime.now().isoformat(),
        })
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_observation(self, observation: str) -> None:
        self.observations.append(observation)
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_thought(self, thought: str) -> None:
        self.thoughts.append(thought)
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def increment_step(self) -> None:
        self.current_step += 1
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_token_usage(self, tokens: int) -> None:
        self.total_tokens += tokens
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def add_latency(self, latency_ms: int) -> None:
        self.total_latency_ms += latency_ms
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def mark_completed(self, outcome: str = "success") -> None:
        self.is_completed = True
        self.lifecycle_status = "completed"
        self.final_outcome = outcome
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def mark_failed(self, reason: str) -> None:
        self.is_failed = True
        self.lifecycle_status = "failed"
        self.final_outcome = f"failed: {reason}"
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def mark_waiting(self, reason: str) -> None:
        self.final_outcome = reason
        self.lifecycle_status = "waiting_for_user"
        self.refresh_memory_summary()
        self.updated_at = datetime.now()

    def is_current_page_task(self) -> bool:
        instruction = self.instruction or ""
        return any(
            keyword in instruction
            for keyword in ["当前页面", "读取当前", "当前美团招聘页面", "当前标签页", "当前网页"]
        )

    def requires_application_evidence(self) -> bool:
        instruction = self.instruction or ""
        return any(
            keyword in instruction
            for keyword in ["已投递", "投递记录", "岗位名称", "投递状态", "投递时间", "申请记录"]
        )

    def has_application_evidence(self) -> bool:
        target_keywords = ["已投递", "投递记录", "申请记录", "我的申请", "个人中心"]
        field_keywords = ["岗位", "职位", "状态", "时间", "日期"]
        for call in reversed(self.tool_calls):
            if call.get("error"):
                continue
            result = call.get("result") or {}
            application_records = result.get("application_records")
            if isinstance(application_records, list) and application_records:
                return True
            content = str(result.get("content", "")).strip()
            if not content:
                continue
            if any(keyword in content for keyword in target_keywords) and any(
                keyword in content for keyword in field_keywords
            ):
                return True
        return False

    def has_browser_page_content(self) -> bool:
        return bool((self.browser_context or {}).get("page_content"))

    def to_dict(self) -> dict[str, Any]:
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
            "actions": self.actions,
            "gui_actions": self.gui_actions,
            "errors": self.errors,
            "warnings": self.warnings,
            "observations": self.observations,
            "thoughts": self.thoughts,
            "current_url": self.current_url,
            "current_page_title": self.current_page_title,
            "current_page_source": self.current_page_source,
            "current_site_profile": self.current_site_profile,
            "last_tool_result": self.last_tool_result,
            "browser_context": self.browser_context,
            "scenario_type": self.scenario_type,
            "scenario_context": self.scenario_context,
            "browser_runtime_initialized": self.browser_runtime_initialized,
            "current_goal": self.current_goal,
            "current_subgoal": self.current_subgoal,
            "plan_steps": self.plan_steps,
            "expected_result": self.expected_result,
            "lifecycle_status": self.lifecycle_status,
            "candidate_tools": self.candidate_tools,
            "current_decision": self.current_decision,
            "decision_trace": self.decision_trace,
            "recovery_trace": self.recovery_trace,
            "checkpoints": self.checkpoints,
            "active_checkpoint": self.active_checkpoint,
            "memory_summary": self.memory_summary,
            "environment": self.get_environment_snapshot(),
            "is_completed": self.is_completed,
            "is_failed": self.is_failed,
            "final_outcome": self.final_outcome,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentState":
        state = cls(
            task_id=payload["task_id"],
            instruction=payload["instruction"],
            trajectory_id=payload["trajectory_id"],
            current_step=payload.get("current_step", 0),
            max_steps=payload.get("max_steps", 20),
            total_tokens=payload.get("total_tokens", 0),
            total_latency_ms=payload.get("total_latency_ms", 0),
            retry_count=payload.get("retry_count", 0),
            successful_recoveries=payload.get("successful_recoveries", 0),
            tool_calls=payload.get("tool_calls", []),
            actions=payload.get("actions", []),
            gui_actions=payload.get("gui_actions", []),
            errors=payload.get("errors", []),
            warnings=payload.get("warnings", []),
            observations=payload.get("observations", []),
            thoughts=payload.get("thoughts", []),
            current_url=payload.get("current_url"),
            current_page_title=payload.get("current_page_title"),
            current_page_source=payload.get("current_page_source"),
            current_site_profile=payload.get("current_site_profile"),
            last_tool_result=payload.get("last_tool_result"),
            browser_context=payload.get("browser_context"),
            scenario_type=payload.get("scenario_type"),
            scenario_context=payload.get("scenario_context"),
            browser_runtime_initialized=payload.get("browser_runtime_initialized", False),
            current_goal=payload.get("current_goal"),
            current_subgoal=payload.get("current_subgoal"),
            plan_steps=payload.get("plan_steps", []),
            expected_result=payload.get("expected_result"),
            lifecycle_status=payload.get("lifecycle_status", "planning"),
            candidate_tools=payload.get("candidate_tools", []),
            current_decision=payload.get("current_decision"),
            decision_trace=payload.get("decision_trace", []),
            recovery_trace=payload.get("recovery_trace", []),
            checkpoints=payload.get("checkpoints", []),
            active_checkpoint=payload.get("active_checkpoint"),
            memory_summary=payload.get("memory_summary", {}),
            is_completed=payload.get("is_completed", False),
            is_failed=payload.get("is_failed", False),
            final_outcome=payload.get("final_outcome"),
            created_at=_parse_datetime(payload.get("created_at")),
            updated_at=_parse_datetime(payload.get("updated_at")),
        )
        state.refresh_memory_summary()
        return state
