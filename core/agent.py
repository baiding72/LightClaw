"""Agent harness implementation - Custom ReAct loop without LangGraph."""

import json
from typing import Any, Iterator
from collections.abc import Callable
from uuid import uuid4

from core.policy import ToolGateContext, ToolGateDecision, ToolGateResult, ToolPolicy
from core.state import AgentState
from core.tools.base import BaseTool
from core.memory_scope import infer_memory_scope
from core.memory_candidates import extract_memory_candidate_signals
from core.context_guard import protect_state
from core.retry import call_with_retry
from core.tool_result import ToolExecutionResult, classify_tool_output


DEFAULT_REACT_INSTRUCTIONS = """You are a helpful AI assistant running inside the myClaw.

Use the ReAct loop:
1. Reason about whether the user's request needs a tool.
2. If a tool is needed, call exactly the appropriate tool with structured arguments.
3. Treat tool results as observations, then decide whether another tool is needed.
4. When enough information is available, answer the user directly.

Do not claim that a tool succeeded unless you have seen its observation.
Do not invent file contents or directory listings; use file tools when needed.

=== Data Storage Guidelines ===

1. Memory has two water levels:
   - Short-term/session memory: current conversation history plus compact summaries after trimming.
   - Long-term memory: file-backed personal profile and project MEMORY.md.

2. Personal memory -> use profile tools (save_user_profile/read_user_profile):
   - Cross-session user preferences, identity, answer style, stable work habits.
   - Use save_user_profile with action='merge', action='replace', or action='remove'.
   - Inputs like "我喜欢...", "我更喜欢...", "我习惯...", "我的偏好..." are profile write intents unless the user says they are temporary.
   - Do not store temporary or current-session-only information in personal memory.

3. Project memory -> use note tools (save_note/search_notes/read_note):
   - Project decisions, technical constraints, design notes, badcases, reusable findings.
   - Use save_note with action='append', action='edit', action='delete', or action='clear'.
   - If you read an existing note before changing it, you must finish with save_note(action='edit') before saying it was updated.
   - "临时", "本轮", "当前会话", "不要长期保存", and "不要记忆" mean session-only; do not call long-term memory tools.
   - Do not save passwords, bank card passwords, secrets, tokens, API keys, private keys, or credentials. Refuse to store them.

4. Workspace Files & Code -> use office tools (write_office_file/read_office_file/list_office_files):
   - Source code files
   - Documents, configs, scripts
   - Files that are part of your work/projects
   - Create new files with write_office_file; revise existing files with update_office_file.

5. Task Scheduling -> use task tools (schedule_task/list_tasks/cancel_task):
   - Reminders and recurring tasks
   - Timed notifications

Do NOT mix up the two storage systems: notes are for knowledge, office files are for project work.

6. Source routing:
   - Use notes tools for saved memory, profile tools for user preferences, and office tools for workspace files.
   - Do not search historical run/session traces as a memory source.
   - Use web tools only when the question needs external, current, official, or web page information.
"""


MEMORY_WRITE_TOOLS = {"save_user_profile", "save_note"}
PROFILE_WRITE_TOOLS = {"save_user_profile"}
SUCCESS_MARKERS = ("saved", "updated", "note saved", "note updated", "profile saved", "profile updated")
FAILURE_MARKERS = ("error", "unchanged", "already exists", "paused by policy", "denied", "missing required")
COMMITMENT_MARKERS = (
    "已记住",
    "记住了",
    "我会记住",
    "会记住",
    "已保存",
    "保存了",
    "已更新",
    "更新了",
    "已记录",
    "记录了",
    "记下了",
    "已记下",
    "已把",
    "已将",
    "以后会",
    "会按照",
    "done",
    "saved",
    "updated",
    "remembered",
)
MEMORY_QUERY_MARKERS = ("之前告诉过你", "你记得", "我之前", "我的偏好", "我偏好的", "说说看")
MEMORY_CLAIM_MARKERS = ("我记得", "你说过", "根据你的记忆", "根据已保存", "你之前告诉过")
SENSITIVE_MEMORY_MARKERS = ("银行卡密码", "密码", "secret", "token", "api key", "apikey", "私钥", "密钥", "credential")
REFUSAL_MARKERS = ("不能保存", "不应保存", "不会保存", "无法保存", "不能记住", "不应记住", "不会记住", "敏感凭据", "敏感信息")


def _memory_write_intent(user_input: str) -> bool:
    if _memory_query_intent(user_input) or any(marker in user_input for marker in ("什么", "？", "?")):
        return False
    decision = infer_memory_scope(user_input, "save_user_profile")
    if decision.intent in {"write", "update"} and decision.scope in {"profile", "session"}:
        return True
    note_decision = infer_memory_scope(user_input, "save_note")
    return note_decision.intent in {"write", "update"} and note_decision.scope == "note"


def _sensitive_memory_intent(user_input: str) -> bool:
    lowered = user_input.lower()
    return any(marker in lowered for marker in SENSITIVE_MEMORY_MARKERS) and any(marker in user_input for marker in ("记住", "保存", "记录"))


def _memory_query_intent(user_input: str) -> bool:
    return any(marker in user_input for marker in MEMORY_QUERY_MARKERS)


def _result_succeeded(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in SUCCESS_MARKERS) and not any(marker in lowered for marker in FAILURE_MARKERS)


def _message_succeeded(message: Any) -> bool:
    metadata = getattr(message, "metadata", {}) or {}
    if "tool_ok" in metadata:
        return bool(metadata["tool_ok"])
    return _result_succeeded(getattr(message, "content", "") or "")


def _result_failed(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in FAILURE_MARKERS)


def _message_failed(message: Any) -> bool:
    metadata = getattr(message, "metadata", {}) or {}
    if "tool_ok" in metadata:
        return not bool(metadata["tool_ok"])
    return _result_failed(getattr(message, "content", "") or "")


def _commits_success(text: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in COMMITMENT_MARKERS)


def _claims_memory(text: str) -> bool:
    return any(marker in text for marker in MEMORY_CLAIM_MARKERS)


def _refuses_sensitive_memory(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def _auto_profile_write_args(user_input: str) -> dict[str, str] | None:
    decision = infer_memory_scope(user_input, "save_user_profile")
    if decision.scope != "profile" or decision.intent not in {"write", "update"}:
        return None
    if decision.confidence < 0.7 or _sensitive_memory_intent(user_input):
        return None
    if _memory_query_intent(user_input) or any(marker in user_input for marker in ("什么", "？", "?")):
        return None
    write_signals = ("我喜欢", "我更喜欢", "我偏好", "我习惯", "我的偏好", "请记住", "记住：")
    if not any(signal in user_input for signal in write_signals):
        return None
    return {
        "action": "merge",
        "new_content": f"- 用户偏好: {user_input.strip()}",
    }


def _auto_note_write_args(user_input: str) -> dict[str, str] | None:
    decision = infer_memory_scope(user_input, "save_note")
    if decision.scope != "note" or decision.intent != "write":
        return None
    if decision.confidence < 0.7 or _sensitive_memory_intent(user_input):
        return None
    if _memory_query_intent(user_input) or any(marker in user_input for marker in ("什么", "？", "?")):
        return None
    write_signals = ("项目约定", "项目规范", "项目决策", "记下来", "记住", "记录")
    if not any(signal in user_input for signal in write_signals):
        return None
    return {
        "action": "append",
        "title": "项目约定" if "项目约定" in user_input else "项目记忆",
        "content": user_input.strip(),
    }


class AgentHarness:
    """Custom ReAct agent harness - no LangGraph dependency.

    Implements the ReAct pattern with a simple while loop:
    - Think: LLM decides if a tool is needed
    - Act: Execute tool if needed
    - Observe: Feed tool result back to LLM
    - Repeat until final answer
    """

    def __init__(
        self,
        llm: Any,
        tools: list[BaseTool] | None = None,
        system_prompt: str | None = None,
        max_turns: int = 10,
        tool_policy: ToolPolicy | None = None,
        approval_callback: Callable[[ToolGateContext, ToolGateResult], bool] | None = None,
    ):
        """Initialize the agent harness.

        Args:
            llm: Chat model instance (must have bind_tools and stream/invoke methods).
            tools: List of tools. Defaults to built-in tools.
            system_prompt: Custom system prompt.
            max_turns: Maximum ReAct turns to prevent infinite loops.
        """
        self.llm = llm
        self.tools = list(tools) if tools else []
        self.max_turns = max_turns
        self.tool_policy = tool_policy or ToolPolicy()
        self.approval_callback = approval_callback
        self.last_gate_events: list[dict[str, Any]] = []
        self.last_memory_context_loaded = False
        self.enable_tool_calling = len(self.tools) > 0

        # Build tool schemas for LLM
        self.tool_schemas = [t.get_schema() if hasattr(t, 'get_schema') else {"name": t.name, "description": t.description, "parameters": {"type": "object", "properties": {}, "required": []}} for t in self.tools]
        self.tool_map = {t.name: t for t in self.tools}

        # Build system prompt
        tool_lines = []
        for schema in self.tool_schemas:
            tool_lines.append(f"- {schema['name']}: {schema['description']}")

        self.system_prompt = system_prompt or (DEFAULT_REACT_INSTRUCTIONS + "\nAvailable tools:\n" + "\n".join(tool_lines))

    # ==========================================
    # Convenience Methods - Tool Management
    # ==========================================

    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to the agent dynamically.

        Args:
            tool: A BaseTool instance to add.
        """
        if tool.name in self.tool_map:
            print(f"⚠️ Tool '{tool.name}' already exists, replacing")
        self.tools.append(tool)
        self.tool_map[tool.name] = tool
        self.tool_schemas.append(tool.get_schema())
        self.enable_tool_calling = True
        print(f"🔧 Tool '{tool.name}' added")

    def has_tools(self) -> bool:
        """Check if the agent has any tools registered.

        Returns:
            True if tools are available for tool calling.
        """
        return self.enable_tool_calling and len(self.tools) > 0

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the agent by name.

        Args:
            tool_name: Name of the tool to remove.

        Returns:
            True if tool was removed, False if not found.
        """
        for i, t in enumerate(self.tools):
            if t.name == tool_name:
                self.tools.pop(i)
                self.tool_map.pop(tool_name, None)
                self.tool_schemas = [s for s in self.tool_schemas if s.get("name") != tool_name]
                print(f"✓ Tool '{tool_name}' removed")
                return True
        return False

    def list_tools(self) -> list[str]:
        """List all available tool names.

        Returns:
            List of tool names currently registered.
        """
        return [t.name for t in self.tools]

    # ==========================================
    # Core Methods
    # ==========================================

    def _build_messages(self, state: AgentState) -> list[dict]:
        """Build messages for LLM from agent state."""
        messages = []
        system_parts = [self.system_prompt]

        # Inject compact long-term memory files if available (loaded each turn for freshness).
        memory_context = self._load_memory_context()
        self.last_memory_context_loaded = bool(memory_context.strip())
        if memory_context:
            system_parts.append(memory_context)

        # If there's a context summary (from trimming), prepend it as a system message
        if state.summary:
            system_parts.append(state.summary)

        # Some OpenAI-compatible providers reject tool calling when multiple
        # system messages are present. Keep dynamic injections, but fold them
        # into one system message for provider compatibility.
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

        # Conversation messages - use Message.to_dict() for OpenAI compatibility
        for msg in state.messages:
            messages.append(msg.to_dict())

        return messages

    def _load_user_profile(self) -> str:
        """Load the user's long-term profile from disk, if it exists."""
        try:
            from core.config import MEMORY_DIR

            profile_path = MEMORY_DIR / "profile.md"
            if profile_path.exists():
                content = profile_path.read_text(encoding="utf-8").strip()
                return content if content else ""
        except Exception:
            pass
        return ""

    def _load_memory_context(self) -> str:
        """Load compact long-term memory context for prompt injection."""
        try:
            from core.config import MEMORY_DIR

            parts: list[str] = []
            legacy_profile = self._load_user_profile()
            if legacy_profile:
                parts.append(f"[User Profile]\n{legacy_profile}")

            project_index = MEMORY_DIR / "MEMORY.md"
            if project_index.exists():
                content = project_index.read_text(encoding="utf-8").strip()
                if content:
                    parts.append(f"[Project Memory]\n{content}")
            return "\n\n".join(parts)
        except Exception:
            return self._load_user_profile()

    def _initialize_state(self, user_input: str, history: list[dict[str, str]] | None = None) -> AgentState:
        state = AgentState()
        for item in history or []:
            role = item.get("role")
            content = str(item.get("content", ""))
            if not content:
                continue
            if role == "user":
                state.add_user_message(content)
            elif role == "assistant":
                state.add_ai_message(content)
        state.add_user_message(user_input)
        return state

    def _apply_completion_hook(self, user_input: str, answer: str, state: AgentState) -> tuple[str, list[dict[str, Any]]]:
        hook_events: list[dict[str, Any]] = []
        tool_results = [message for message in state.messages if message.role == "tool"]
        memory_results = [message for message in tool_results if message.name in MEMORY_WRITE_TOOLS]
        successful_memory_write = any(_message_succeeded(message) for message in memory_results)
        failed_results = [message for message in tool_results if _message_failed(message)]
        tool_calls = [
            call
            for message in state.messages
            if message.role == "assistant"
            for call in (message.tool_calls or [])
        ]
        note_read_used = any(message.name in {"read_note", "search_notes"} for message in tool_results)
        note_edit_succeeded = any(
            call.get("name") == "save_note"
            and str((call.get("args") or {}).get("action", "")).lower() == "edit"
            and _message_succeeded(result)
            for call in tool_calls
            for result in tool_results
            if result.name == "save_note"
        )

        if _sensitive_memory_intent(user_input) and (
            not _refuses_sensitive_memory(answer) or "不能保存" not in answer
        ):
            corrected = "我不能保存银行卡密码、密码、secret、token 或 API key 这类敏感凭据。"
            hook_events.append(
                {
                    "hook": "sensitive_memory_refusal_guard",
                    "reason": "sensitive credential memory request must be refused",
                    "original_answer_preview": answer[:500],
                    "replacement_answer": corrected,
                }
            )
            return corrected, hook_events

        if _memory_query_intent(user_input) and not self.last_memory_context_loaded and _claims_memory(answer):
            corrected = "我目前没有可用的已保存记忆，所以不能声称记得你之前告诉过我的偏好。"
            hook_events.append(
                {
                    "hook": "no_memory_fabrication_guard",
                    "reason": "answer claimed memory without loaded memory context",
                    "original_answer_preview": answer[:500],
                    "replacement_answer": corrected,
                }
            )
            return corrected, hook_events

        note_decision = infer_memory_scope(user_input, "save_note")
        if (
            note_decision.intent == "update"
            and note_read_used
            and not note_edit_succeeded
            and _commits_success(answer)
        ):
            corrected = (
                "我没有更新这条项目记忆。本轮虽然读取了已有 note，"
                "但没有看到 save_note(action='edit') 的成功结果。"
            )
            hook_events.append(
                {
                    "hook": "read_modify_write_guard",
                    "reason": "note update claim without successful save_note(action=edit)",
                    "original_answer_preview": answer[:500],
                    "replacement_answer": corrected,
                }
            )
            return corrected, hook_events

        if _memory_write_intent(user_input) and not successful_memory_write and _commits_success(answer):
            corrected = (
                "我没有保存或更新这条记忆。本轮没有看到成功的记忆写入结果，"
                "所以不能声称已经记住、保存或更新。"
            )
            hook_events.append(
                {
                    "hook": "memory_commitment_guard",
                    "reason": "memory intent without successful memory write",
                    "original_answer_preview": answer[:500],
                    "replacement_answer": corrected,
                }
            )
            return corrected, hook_events

        if failed_results and _commits_success(answer):
            corrected = (
                "这次操作没有成功完成。工具返回了失败、未变更或被策略拦截的结果，"
                "所以我不能声称已经完成。"
            )
            hook_events.append(
                {
                    "hook": "tool_success_guard",
                    "reason": "answer claimed success after failed tool result",
                    "failed_tools": [message.name for message in failed_results],
                    "original_answer_preview": answer[:500],
                    "replacement_answer": corrected,
                }
            )
            return corrected, hook_events

        return answer, hook_events

    def _apply_auto_memory_write(self, user_input: str, state: AgentState, react_step: int = 1) -> dict[str, Any] | None:
        """Persist obvious memory-write statements before the LLM can merely acknowledge them."""
        tool_name = ""
        args = _auto_profile_write_args(user_input)
        if args and "save_user_profile" in self.tool_map:
            tool_name = "save_user_profile"
        else:
            args = _auto_note_write_args(user_input)
            if args and "save_note" in self.tool_map:
                tool_name = "save_note"
        if not args or not tool_name:
            return None

        tool_call_id = f"auto_memory_{uuid4().hex[:8]}"
        state.add_ai_message(
            content="",
            tool_calls=[
                {
                    "name": tool_name,
                    "args": args,
                    "id": tool_call_id,
                }
            ],
        )
        tool_result, gate = self._execute_tool_structured(
            tool_name,
            args,
            user_input=user_input,
            react_step=react_step,
            tool_call_id=tool_call_id,
        )
        state.add_tool_message(
            name=tool_name,
            content=tool_result.to_observation(),
            tool_call_id=tool_call_id,
            metadata=tool_result.to_trace(),
        )
        return {
            "tool": tool_name,
            "args": args,
            "tool_call_id": tool_call_id,
            "result": tool_result.to_observation(),
            "structured_result": tool_result,
            "gate": gate,
        }

    def _check_tool_gate(self, tool_name: str, args: dict, user_input: str = "", react_step: int | None = None) -> ToolGateResult:
        """Evaluate the configured permission policy before tool execution."""
        return self.tool_policy.evaluate(
            ToolGateContext(
                tool_name=tool_name,
                args=args,
                user_input=user_input,
                react_step=react_step,
            )
        )

    def _execute_tool_structured(
        self,
        tool_name: str,
        args: dict,
        user_input: str = "",
        react_step: int | None = None,
        tool_call_id: str | None = None,
    ) -> tuple[ToolExecutionResult, ToolGateResult]:
        """Execute a tool by name with arguments."""
        context = ToolGateContext(
            tool_name=tool_name,
            args=args,
            user_input=user_input,
            react_step=react_step,
        )
        gate = self.tool_policy.evaluate(context)
        if gate.decision == ToolGateDecision.ASK and self.approval_callback:
            approved = self.approval_callback(context, gate)
            if approved:
                gate = ToolGateResult(
                    decision=ToolGateDecision.ALLOW,
                    permission=gate.permission,
                    reason="用户已在前端确认允许执行",
                    mode=gate.mode,
                    metadata={**gate.metadata, "approved_by_user": True},
                )
            else:
                gate = ToolGateResult(
                    decision=ToolGateDecision.DENY,
                    permission=gate.permission,
                    reason="用户拒绝或确认超时，工具未执行",
                    mode=gate.mode,
                    metadata={**gate.metadata, "approved_by_user": False},
                )
        if gate.mode != "off":
            self.last_gate_events.append({"tool_name": tool_name, "tool_args": args, "tool_call_id": tool_call_id, **gate.to_trace()})
        if gate.decision != ToolGateDecision.ALLOW:
            text = f"Tool execution paused by policy: {gate.decision.value}. Permission={gate.permission.key}. Reason={gate.reason}"
            return (
                classify_tool_output(tool_name, text, denied=True),
                gate,
            )

        if tool_name not in self.tool_map:
            return classify_tool_output(tool_name, f"Error: Unknown tool '{tool_name}'"), gate

        tool = self.tool_map[tool_name]

        # Pre-validation: check required params before invoking
        schema = tool.get_schema()
        required = schema.get("parameters", {}).get("required", [])
        missing = [p for p in required if p not in args or args[p] is None]
        if missing:
            return classify_tool_output(
                tool_name,
                f"Error: {tool_name}() missing required argument(s): {', '.join(missing)}. Required: {required}",
            ), gate

        try:
            clean_args = {key: value for key, value in args.items() if not key.startswith("_")}
            result = tool.invoke(**clean_args)
            text = str(result) if result is not None else "Tool executed successfully"
            return classify_tool_output(tool_name, text), gate
        except Exception as e:
            return classify_tool_output(tool_name, f"Error: {str(e)}"), gate

    def _execute_tool(
        self,
        tool_name: str,
        args: dict,
        user_input: str = "",
        react_step: int | None = None,
        tool_call_id: str | None = None,
    ) -> tuple[str, ToolGateResult]:
        """Backward-compatible tool executor returning plain observation text."""
        result, gate = self._execute_tool_structured(
            tool_name,
            args,
            user_input=user_input,
            react_step=react_step,
            tool_call_id=tool_call_id,
        )
        return result.to_observation(), gate

    def run(self, user_input: str, verbose: bool = False, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        """Run the ReAct agent loop (non-streaming).

        Args:
            user_input: User's input message.
            verbose: If True, print trace at each step.

        Returns:
            Dict with 'answer' (final response text) and 'state' (final AgentState).
        """
        # Accumulate full response for non-streaming
        full_content = ""
        self.last_gate_events = []
        context_guard_events: list[dict[str, Any]] = []
        memory_candidate_events = [
            signal.to_trace()
            for signal in extract_memory_candidate_signals(user_input, history)
        ]

        # Initialize state
        state = self._initialize_state(user_input, history)
        self.last_gate_events = []

        auto_write = self._apply_auto_memory_write(user_input, state, react_step=1)
        if auto_write and auto_write["gate"].decision != ToolGateDecision.ALLOW:
            answer = "工具调用被拒绝、等待确认或确认超时，本轮已暂停。"
            state.add_ai_message(content=answer)
            return {
                "answer": answer,
                "state": state,
                "turns": 1,
                "tool_gate_events": list(self.last_gate_events),
                "hook_events": [],
                "context_guard_events": context_guard_events,
                "memory_candidate_events": memory_candidate_events,
            }

        # Context trimming: check if we need to trim old messages
        context_report = protect_state(state)
        if context_report.compacted_tool_results or context_report.trimmed:
            context_guard_events.append(
                {
                    "estimated_tokens_before": context_report.estimated_tokens_before,
                    "estimated_tokens_after": context_report.estimated_tokens_after,
                    "compacted_tool_results": context_report.compacted_tool_results,
                    "trimmed": context_report.trimmed,
                    "summary": context_report.summary,
                }
            )
        if state.count_turns() > 1:
            from core.state import CONTEXT_TRIM_TRIGGER
            if len(state.messages) > CONTEXT_TRIM_TRIGGER:
                state.trim_context()

        if verbose:
            print(f"[Turn 0] User: {user_input}")

        # ReAct loop
        for turn in range(self.max_turns):
            # Build messages for LLM
            messages = self._build_messages(state)

            # Invoke LLM with tools - pass schemas for binding
            self.llm_with_tools = self.llm.bind_tools(self.tool_schemas)
            response = call_with_retry(lambda: self.llm_with_tools.invoke(messages))

            # Extract response
            response_content = getattr(response, "content", "") or ""
            response_tool_calls = getattr(response, "tool_calls", None) or []
            full_content += response_content

            if verbose:
                print(f"[Turn {turn + 1}] AI response length: {len(response_content)}, tool_calls: {len(response_tool_calls)}")

            # Check if LLM wants to call tools
            if response_tool_calls:
                # Add AI message with tool calls to state
                state.add_ai_message(
                    content=response_content,
                    tool_calls=[{
                        "name": tc.get("name"),
                        "args": tc.get("args", {}),
                        "id": tc.get("id"),
                    } for tc in response_tool_calls]
                )

                # Execute each tool
                for tc in response_tool_calls:
                    tool_name = tc.get("name")
                    args = tc.get("args", {})
                    tool_call_id = tc.get("id")

                    if verbose:
                        print(f"  -> Calling {tool_name} with args={args}")

                    tool_result, gate = self._execute_tool_structured(
                        tool_name,
                        args,
                        user_input=user_input,
                        react_step=turn + 1,
                        tool_call_id=tool_call_id,
                    )

                    if verbose:
                        print(f"  <- {tool_result.output[:100]}...")

                    state.add_tool_message(
                        name=tool_name,
                        content=tool_result.to_observation(),
                        tool_call_id=tool_call_id,
                        metadata=tool_result.to_trace(),
                    )
                    if gate.decision != ToolGateDecision.ALLOW:
                        answer = "工具调用被拒绝、等待确认或确认超时，本轮已暂停。"
                        state.add_ai_message(content=answer)
                        return {
                            "answer": answer,
                            "state": state,
                            "turns": turn + 1,
                            "tool_gate_events": list(self.last_gate_events),
                            "hook_events": [],
                            "context_guard_events": context_guard_events,
                            "memory_candidate_events": memory_candidate_events,
                        }

                # Continue to next turn
                continue

            # No tool calls - this is the final answer
            if response_content:
                final_answer, hook_events = self._apply_completion_hook(user_input, full_content, state)
                state.add_ai_message(content=final_answer)
                if verbose:
                    print(f"[Turn {turn + 1}] Final answer: {final_answer[:100]}...")

                return {
                    "answer": final_answer,
                    "state": state,
                    "turns": turn + 1,
                    "tool_gate_events": list(self.last_gate_events),
                    "hook_events": hook_events,
                    "context_guard_events": context_guard_events,
                    "memory_candidate_events": memory_candidate_events,
                }

            # Empty response with no tools - something went wrong
            if verbose:
                print(f"[Turn {turn + 1}] Empty response, stopping")

            return {
                "answer": "(No response from agent)",
                "state": state,
                "turns": turn + 1,
                "tool_gate_events": list(self.last_gate_events),
                "hook_events": [],
                "context_guard_events": context_guard_events,
                "memory_candidate_events": memory_candidate_events,
            }

        # Max turns reached
        return {
            "answer": f"(ReAct loop reached max turns ({self.max_turns}))",
            "state": state,
            "turns": self.max_turns,
            "tool_gate_events": list(self.last_gate_events),
            "hook_events": [],
            "context_guard_events": context_guard_events,
            "memory_candidate_events": memory_candidate_events,
        }

    def stream(self, user_input: str, verbose: bool = False, history: list[dict[str, str]] | None = None) -> Iterator[dict[str, Any]]:
        """Run the ReAct agent loop with streaming output.

        Yields events as they happen:
        - {"type": "content", "content": "..."} - streaming content chunks
        - {"type": "tool_call", "tool": "...", "args": {...}} - tool call detected
        - {"type": "tool_result", "tool": "...", "result": "..."} - tool result
        - {"type": "final", "answer": "...", "turns": N} - final answer

        Args:
            user_input: User's input message.
            verbose: If True, print trace.

        Yields:
            Event dicts as described above.
        """
        # Initialize state
        state = self._initialize_state(user_input, history)
        self.last_gate_events = []
        memory_candidate_events = [
            signal.to_trace()
            for signal in extract_memory_candidate_signals(user_input, history)
        ]
        for candidate_event in memory_candidate_events:
            yield {
                "type": "memory_candidate_signal",
                **candidate_event,
            }

        auto_write = self._apply_auto_memory_write(user_input, state, react_step=1)
        if auto_write:
            yield {
                "type": "tool_call",
                "tool": auto_write["tool"],
                "args": auto_write["args"],
                "tool_call_id": auto_write["tool_call_id"],
                "react_step": 1,
            }
            if auto_write["gate"].mode != "off":
                yield {
                    "type": "tool_gate_decision",
                    "tool": auto_write["tool"],
                    "args": auto_write["args"],
                    "tool_call_id": auto_write["tool_call_id"],
                    "react_step": 1,
                    **auto_write["gate"].to_trace(),
                }
            yield {
                "type": "tool_result",
                "tool": auto_write["tool"],
                "result": auto_write["result"],
                "tool_call_id": auto_write["tool_call_id"],
                "react_step": 1,
            }
            if auto_write["gate"].decision != ToolGateDecision.ALLOW:
                answer = "工具调用被拒绝、等待确认或确认超时，本轮已暂停。"
                state.add_ai_message(content=answer)
                yield {
                    "type": "final",
                    "answer": answer,
                    "state": state,
                    "turns": 1,
                    "react_step": 1,
                    "tool_gate_events": list(self.last_gate_events),
                    "hook_events": [],
                    "memory_candidate_events": memory_candidate_events,
                }
                return

        # Context trimming: check if we need to trim old messages
        context_report = protect_state(state)
        if context_report.compacted_tool_results or context_report.trimmed:
            yield {
                "type": "context_guard",
                "estimated_tokens_before": context_report.estimated_tokens_before,
                "estimated_tokens_after": context_report.estimated_tokens_after,
                "compacted_tool_results": context_report.compacted_tool_results,
                "trimmed": context_report.trimmed,
                "summary": context_report.summary,
            }
        if state.count_turns() > 1:  # Only check after first turn
            from core.state import CONTEXT_TRIM_TRIGGER
            if len(state.messages) > CONTEXT_TRIM_TRIGGER:
                summary = state.trim_context()
                if summary:
                    yield {
                        "type": "context_trimmed",
                        "summary": summary,
                        "message_count_after": len(state.messages),
                    }

        if verbose:
            print(f"[Turn 0] User: {user_input}")

        # ReAct loop
        for turn in range(1, self.max_turns + 1):
            # Build messages for LLM
            messages = self._build_messages(state)
            yield {
                "type": "llm_input",
                "react_step": turn,
                "message_count": len(messages),
                "state_message_count": len(state.messages),
                "message_types": [message.get("role", "unknown") for message in messages],
                "messages": messages,
            }

            # Invoke LLM with streaming
            self.llm_with_tools = self.llm.bind_tools(self.tool_schemas)

            # Try streaming first
            try:
                stream_response = self.llm_with_tools.stream(messages)
                full_content = ""
                merged_chunk = None

                for chunk in stream_response:
                    if merged_chunk is None:
                        merged_chunk = chunk
                    else:
                        try:
                            merged_chunk = merged_chunk + chunk
                        except TypeError:
                            pass

                    chunk_content = getattr(chunk, "content", "") or ""

                    if chunk_content:
                        full_content += chunk_content
                        yield {"type": "content", "content": chunk_content, "react_step": turn}

                # LangChain streams tool calls as partial chunks. Only execute
                # after the final AIMessageChunk has merged them into complete
                # tool call objects.
                response_tool_calls = getattr(merged_chunk, "tool_calls", None) or []

            except (AttributeError, TypeError):
                # Fallback to non-streaming if stream not supported
                response = self.llm_with_tools.invoke(messages)
                full_content = getattr(response, "content", "") or ""
                response_tool_calls = getattr(response, "tool_calls", None) or []

                yield {"type": "content", "content": full_content, "react_step": turn}

            if verbose:
                print(f"[Turn {turn}] AI content length: {len(full_content)}, tool_calls: {len(response_tool_calls)}")

            # Handle tool calls
            if response_tool_calls:
                response_tool_calls = [
                    tc for tc in response_tool_calls
                    if tc.get("name") and isinstance(tc.get("args", {}), dict)
                ]
            if response_tool_calls:
                state.add_ai_message(
                    content=full_content,
                    tool_calls=[{
                        "name": tc.get("name"),
                        "args": tc.get("args", {}),
                        "id": tc.get("id"),
                    } for tc in response_tool_calls]
                )

                # Execute each tool
                for tc in response_tool_calls:
                    tool_name = tc.get("name")
                    args = tc.get("args", {})
                    tool_call_id = tc.get("id")

                    if verbose:
                        print(f"  -> Calling {tool_name} with args={args}")

                    yield {"type": "tool_call", "tool": tool_name, "args": args, "tool_call_id": tool_call_id, "react_step": turn}

                    tool_result, gate = self._execute_tool_structured(
                        tool_name,
                        args,
                        user_input=user_input,
                        react_step=turn,
                        tool_call_id=tool_call_id,
                    )
                    if gate.mode != "off":
                        yield {
                            "type": "tool_gate_decision",
                            "tool": tool_name,
                            "args": args,
                            "tool_call_id": tool_call_id,
                            "react_step": turn,
                            **gate.to_trace(),
                        }

                    if verbose:
                        print(f"  <- {tool_result.output[:100]}...")

                    yield {
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": tool_result.to_observation(),
                        "structured_result": tool_result.to_trace(),
                        "tool_call_id": tool_call_id,
                        "react_step": turn,
                    }

                    state.add_tool_message(
                        name=tool_name,
                        content=tool_result.to_observation(),
                        tool_call_id=tool_call_id,
                        metadata=tool_result.to_trace(),
                    )

                    if gate.decision != ToolGateDecision.ALLOW:
                        answer = "工具调用被拒绝、等待确认或确认超时，本轮已暂停。"
                        state.add_ai_message(content=answer)
                        yield {
                            "type": "final",
                            "answer": answer,
                            "state": state,
                            "turns": turn,
                            "react_step": turn,
                            "tool_gate_events": list(self.last_gate_events),
                            "hook_events": [],
                            "memory_candidate_events": memory_candidate_events,
                        }
                        return

                # Continue to next turn
                continue

            # No tool calls - final answer
            if full_content:
                final_answer, hook_events = self._apply_completion_hook(user_input, full_content, state)
                state.add_ai_message(content=final_answer)
                if verbose:
                    print(f"[Turn {turn}] Final answer: {final_answer[:100]}...")

                yield {"type": "final", "answer": final_answer, "state": state, "turns": turn, "react_step": turn, "tool_gate_events": list(self.last_gate_events), "hook_events": hook_events, "memory_candidate_events": memory_candidate_events}
                return

            # Empty response
            if verbose:
                print(f"[Turn {turn}] Empty response, stopping")

            yield {"type": "final", "answer": "(No response from agent)", "state": state, "turns": turn, "react_step": turn, "tool_gate_events": list(self.last_gate_events), "hook_events": [], "memory_candidate_events": memory_candidate_events}
            return

        # Max turns reached
        yield {"type": "final", "answer": f"(ReAct loop reached max turns ({self.max_turns}))", "state": state, "turns": self.max_turns, "react_step": self.max_turns, "tool_gate_events": list(self.last_gate_events), "hook_events": [], "memory_candidate_events": memory_candidate_events}


def create_agent_harness(
    llm: Any,
    tools: list[BaseTool] | None = None,
    system_prompt: str | None = None,
    max_turns: int = 10,
    tool_policy: ToolPolicy | None = None,
    approval_callback: Callable[[ToolGateContext, ToolGateResult], bool] | None = None,
) -> AgentHarness:
    """Factory function to create an AgentHarness instance.

    Args:
        llm: Chat model instance.
        tools: List of tools.
        system_prompt: Custom system prompt.
        max_turns: Maximum ReAct turns.

    Returns:
        AgentHarness instance.
    """
    from core.tools import ALL_TOOLS
    actual_tools = tools if tools is not None else ALL_TOOLS

    return AgentHarness(
        llm=llm,
        tools=actual_tools,
        system_prompt=system_prompt,
        max_turns=max_turns,
        tool_policy=tool_policy,
        approval_callback=approval_callback,
    )
