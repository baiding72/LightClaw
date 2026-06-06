#!/usr/bin/env python3
"""Run one interactive myClaw turn and append trace to a session run log.

Supports two modes:
- Normal mode: Returns single JSON result (backward compatible)
- Stream mode (--stream): Emits JSONL lines for real-time streaming
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from uuid import uuid4

from core.agent import create_agent_harness
from core.config import APPROVALS_DIR, load_policy_config
from core.checkpoint import clear_checkpoint, write_checkpoint
from core.logger import RunLogger
from core.policy import ToolGateContext, ToolGateResult
from core.provider import get_provider


REPO_ROOT = Path(__file__).resolve().parent
MYCLAW_DIR = REPO_ROOT
ENV_PATH = MYCLAW_DIR / ".env"
SESSIONS_DIR = MYCLAW_DIR / "sessions"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def safe_session_id(session_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", session_id.strip())
    return cleaned[:80] or "default"


def session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{safe_session_id(session_id)}.json"


def session_events_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{safe_session_id(session_id)}.jsonl"


def append_session_event(session_id: str, event: str, **fields: object) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": time.time(),
        "session_id": safe_session_id(session_id),
        "event": event,
        **fields,
    }
    with session_events_path(session_id).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def load_transcript(session_id: str) -> list[dict[str, str]]:
    path = session_path(session_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [
        {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
        for item in data
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
    ]


def save_transcript(session_id: str, transcript: list[dict[str, str]]) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_path(session_id).write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")


def next_conversation_turn(transcript: list[dict[str, str]]) -> int:
    """Return the 1-based user turn index for the next input."""
    return sum(1 for item in transcript if item.get("role") == "user") + 1


def compact_message_preview(message: dict) -> dict[str, str]:
    content = str(message.get("content", ""))
    return {
        "type": str(message.get("role", message.get("type", "unknown"))),
        "content_preview": content[:200],
    }


def load_user_profile_content() -> str:
    from core.config import MEMORY_DIR

    profile_path = MEMORY_DIR / "profile.md"
    try:
        if profile_path.exists():
            return profile_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    return ""


def load_memory_injection_events() -> list[dict[str, str]]:
    from core.config import MEMORY_DIR

    candidates = [
        ("memory.profile", MEMORY_DIR / "profile.md"),
        ("memory.project", MEMORY_DIR / "MEMORY.md"),
    ]

    events: list[dict[str, str]] = []
    for resource, path in candidates:
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    events.append({"resource": resource, "content_preview": content[:500]})
        except Exception:
            continue
    return events


def emit_event(event_type: str, data: dict) -> None:
    """Emit a JSONL line for streaming mode."""
    line = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    print(line, flush=True)


def approval_path(request_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", request_id)
    return APPROVALS_DIR / f"{safe_id}.json"


def wait_for_tool_approval(
    context: ToolGateContext,
    gate: ToolGateResult,
    *,
    session_id: str,
    conversation_turn: int,
) -> bool:
    request_id = f"{session_id}-{conversation_turn}-{context.react_step or 0}-{uuid4().hex[:8]}"
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    path = approval_path(request_id)
    if path.exists():
        path.unlink()

    payload = {
        "request_id": request_id,
        "session_id": session_id,
        "conversation_turn": conversation_turn,
        "react_step": context.react_step,
        "react_phase": "policy",
        "tool_name": context.tool_name,
        "tool_args": context.args,
        "tool_gate_decision": gate.decision.value,
        **gate.to_trace(),
    }
    emit_event("tool_gate_decision", payload)

    timeout = int(load_policy_config().get("approval_timeout_seconds", 300))
    deadline = time.time() + max(1, timeout)
    while time.time() < deadline:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return False
            finally:
                try:
                    path.unlink()
                except OSError:
                    pass
            return str(data.get("decision", "")).lower() == "allow"
        time.sleep(0.2)
    return False


def run_turn_stream(session_id: str, message: str) -> None:
    """Run turn in streaming mode - outputs JSONL lines."""
    load_env_file(ENV_PATH)

    provider_name = os.environ.get("MYCLAW_PROVIDER", "openai")
    model_name = os.environ.get("MYCLAW_MODEL")
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_API_BASE")

    safe_id = safe_session_id(session_id)
    logger = RunLogger(run_id=f"interactive-{safe_id}")

    run_already_exists = logger.path.exists()
    if not run_already_exists:
        logger.log_event(
            "interactive_session_started",
            session_id=safe_id,
            provider=provider_name,
            model=model_name,
        )

    transcript = load_transcript(safe_id)
    conversation_turn = next_conversation_turn(transcript)

    # Build conversation history
    history = []
    for item in transcript:
        if item["role"] == "user":
            history.append({"type": "human", "content": item["content"]})
        elif item["role"] == "assistant":
            history.append({"type": "ai", "content": item["content"]})

    emit_event("session_started", {
        "session_id": safe_id,
        "run_id": logger.run_id,
        "history_turns": len(history),
        "conversation_turn": conversation_turn,
    })

    llm = get_provider(
        provider_name=provider_name,
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )

    harness = create_agent_harness(
        llm,
        approval_callback=lambda context, gate: wait_for_tool_approval(
            context,
            gate,
            session_id=safe_id,
            conversation_turn=conversation_turn,
        ),
    )

    emit_event("user_input", {
        "session_id": safe_id,
        "content_preview": message[:500],
        "conversation_turn": conversation_turn,
    })
    logger.log_event(
        "user_input",
        session_id=safe_id,
        content_preview=message[:500],
        history_turns=len(history),
        conversation_turn=conversation_turn,
    )
    append_session_event(
        safe_id,
        "user_input",
        content=message,
        content_preview=message[:500],
        conversation_turn=conversation_turn,
    )

    history_msgs = []
    for item in transcript:
        if item["role"] == "user":
            history_msgs.append({"type": "HumanMessage", "content_preview": item["content"]})
        elif item["role"] == "assistant":
            history_msgs.append({"type": "AIMessage", "content_preview": item["content"][:200]})

    memory_events = load_memory_injection_events()
    if not memory_events:
        logger.log_event(
            "memory_context_empty",
            session_id=safe_id,
            conversation_turn=conversation_turn,
        )
    for memory_event in memory_events:
        logger.log_event(
            "memory_injected",
            session_id=safe_id,
            conversation_turn=conversation_turn,
            **memory_event,
        )

    # Stream the agent execution
    final_answer = ""
    final_turns = 0
    final_state = None

    try:
        write_checkpoint(
            safe_id,
            status="llm_streaming",
            conversation_turn=conversation_turn,
            run_id=logger.run_id,
        )
        for event in harness.stream(message, verbose=False, history=transcript):
            event_type = event.get("type")
            react_step = event.get("react_step")

            if event_type == "llm_input":
                raw_messages = event.get("messages", [])
                messages = [compact_message_preview(message) for message in raw_messages if isinstance(message, dict)]
                logger.log_event(
                    "llm_input",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    react_step=react_step,
                    react_phase="input",
                    message_count=event.get("message_count", len(messages)),
                    state_message_count=event.get("state_message_count"),
                    has_summary=False,
                    message_types=event.get("message_types", [m["type"] for m in messages]),
                    messages=messages,
                    )

            elif event_type == "context_guard":
                payload = {
                    key: event.get(key)
                    for key in [
                        "estimated_tokens_before",
                        "estimated_tokens_after",
                        "compacted_tool_results",
                        "trimmed",
                        "summary",
                    ]
                }
                logger.log_event(
                    "context_guard",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    **payload,
                )
                append_session_event(
                    safe_id,
                    "context_guard",
                    conversation_turn=conversation_turn,
                    **payload,
                )

            elif event_type == "memory_candidate_signal":
                payload = {
                    key: event.get(key)
                    for key in [
                        "candidate_key",
                        "candidate_label",
                        "candidate_evidence",
                        "candidate_confidence",
                        "candidate_evidence_count",
                        "candidate_threshold",
                        "candidate_persisted",
                        "would_prompt_for_confirmation",
                        "suppressed",
                        "suppression_reason",
                    ]
                }
                logger.log_event(
                    "memory_candidate_signal",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    react_step=react_step,
                    **payload,
                )
                append_session_event(
                    safe_id,
                    "memory_candidate_signal",
                    conversation_turn=conversation_turn,
                    **payload,
                )
                emit_event("memory_candidate_signal", {
                    "session_id": safe_id,
                    "conversation_turn": conversation_turn,
                    **payload,
                })

            elif event_type == "content":
                chunk = event.get("content", "")
                final_answer += chunk
                emit_event("content_chunk", {
                    "content": chunk,
                    "conversation_turn": conversation_turn,
                    "react_step": react_step,
                    "react_phase": "thought",
                })

            elif event_type == "tool_call":
                logger.log_event(
                    "tool_call",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    react_step=react_step,
                    react_phase="action",
                    tool_name=event.get("tool"),
                    tool_args=event.get("args", {}),
                    tool_call_id=event.get("tool_call_id"),
                )
                append_session_event(
                    safe_id,
                    "tool_call",
                    conversation_turn=conversation_turn,
                    react_step=react_step,
                    tool_name=event.get("tool"),
                    tool_args=event.get("args", {}),
                    tool_call_id=event.get("tool_call_id"),
                )
                emit_event("tool_call", {
                    "session_id": safe_id,
                    "conversation_turn": conversation_turn,
                    "react_step": react_step,
                    "react_phase": "action",
                    "tool_name": event.get("tool"),
                    "tool_args": event.get("args", {}),
                    "tool_call_id": event.get("tool_call_id"),
                })

            elif event_type == "tool_gate_decision":
                gate_trace = {
                    "session_id": safe_id,
                    "conversation_turn": conversation_turn,
                    "react_step": react_step,
                    "react_phase": "policy",
                    "tool_name": event.get("tool"),
                    "tool_args": event.get("args", {}),
                    "tool_call_id": event.get("tool_call_id"),
                    "tool_gate_decision": event.get("decision"),
                    "permission": event.get("permission"),
                    "resource": event.get("resource"),
                    "action": event.get("action"),
                    "scope": event.get("scope"),
                    "risk": event.get("risk"),
                    "requires_consent": event.get("requires_consent"),
                    "reason": event.get("reason"),
                    "policy_mode": event.get("mode"),
                    "memory_scope": event.get("memory_scope"),
                    "memory_scope_confidence": event.get("memory_scope_confidence"),
                    "memory_scope_reason": event.get("memory_scope_reason"),
                    "source_route": event.get("source_route"),
                    "source_route_confidence": event.get("source_route_confidence"),
                    "source_route_reason": event.get("source_route_reason"),
                }
                logger.log_event("tool_gate_decision", **gate_trace)
                emit_event("tool_gate_decision", gate_trace)

            elif event_type == "tool_result":
                structured = event.get("structured_result", {}) if isinstance(event.get("structured_result"), dict) else {}
                logger.log_event(
                    "tool_result",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    react_step=react_step,
                    react_phase="observation",
                    tool_name=event.get("tool"),
                    tool_result=str(event.get("result", ""))[:500],
                    tool_call_id=event.get("tool_call_id"),
                    tool_ok=structured.get("tool_ok"),
                    tool_status=structured.get("tool_status"),
                    tool_metadata=structured.get("tool_metadata"),
                )
                append_session_event(
                    safe_id,
                    "tool_result",
                    conversation_turn=conversation_turn,
                    react_step=react_step,
                    tool_name=event.get("tool"),
                    tool_result=str(event.get("result", ""))[:500],
                    tool_call_id=event.get("tool_call_id"),
                    tool_ok=structured.get("tool_ok"),
                    tool_status=structured.get("tool_status"),
                    tool_metadata=structured.get("tool_metadata"),
                )
                emit_event("tool_result", {
                    "session_id": safe_id,
                    "conversation_turn": conversation_turn,
                    "react_step": react_step,
                    "react_phase": "observation",
                    "tool_name": event.get("tool"),
                    "result": str(event.get("result", ""))[:500],
                    "tool_call_id": event.get("tool_call_id"),
                })

            elif event_type == "final":
                final_answer = event.get("answer", "")
                final_turns = event.get("turns", 0)
                final_state = event.get("state")
                for hook_event in event.get("hook_events", []) or []:
                    logger.log_event(
                        "agent_hook",
                        session_id=safe_id,
                        conversation_turn=conversation_turn,
                        react_step=react_step,
                        **hook_event,
                    )

                logger.log_event(
                    "ai_message",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    react_step=react_step,
                    react_phase="final",
                    content=final_answer,
                    content_preview=final_answer[:500],
                )
                append_session_event(
                    safe_id,
                    "ai_message",
                    conversation_turn=conversation_turn,
                    content=final_answer,
                    content_preview=final_answer[:500],
                )
                emit_event("ai_message", {
                    "session_id": safe_id,
                    "conversation_turn": conversation_turn,
                    "react_step": react_step,
                    "react_phase": "final",
                    "content": final_answer,
                    "content_preview": final_answer[:500],
                })

                logger.log_event(
                    "turn_completed",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    react_step=react_step,
                    react_phase="completed",
                    harness_turns=final_turns,
                    state_message_count=len(final_state.messages) if final_state else len(history_msgs) + 2,
                    has_summary=False,
                    answer_preview=final_answer[:800],
                )
                append_session_event(
                    safe_id,
                    "turn_completed",
                    conversation_turn=conversation_turn,
                    harness_turns=final_turns,
                    answer_preview=final_answer[:800],
                )
                clear_checkpoint(safe_id)
                emit_event("turn_completed", {
                    "session_id": safe_id,
                    "conversation_turn": conversation_turn,
                    "react_step": react_step,
                    "react_phase": "completed",
                    "harness_turns": final_turns,
                    "answer_preview": final_answer[:800],
                })

                # Save transcript
                transcript.append({"role": "user", "content": message})
                transcript.append({"role": "assistant", "content": final_answer})
                save_transcript(safe_id, transcript)
    except Exception as e:
        write_checkpoint(
            safe_id,
            status="error",
            conversation_turn=conversation_turn,
            run_id=logger.run_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        append_session_event(
            safe_id,
            "turn_error",
            conversation_turn=conversation_turn,
            error=str(e),
            error_type=type(e).__name__,
        )
        emit_event("stream_error", {
            "session_id": safe_id,
            "conversation_turn": conversation_turn,
            "error": str(e),
            "error_type": type(e).__name__,
        })
        return

    # Signal completion
    emit_event("stream_complete", {
        "session_id": safe_id,
        "run_id": logger.run_id,
        "run_path": str(logger.path),
        "answer": final_answer,
        "turns": final_turns,
        "conversation_turn": conversation_turn,
    })


def run_turn(session_id: str, message: str) -> dict:
    """Run turn in normal mode - returns single JSON result (backward compatible)."""
    load_env_file(ENV_PATH)

    provider_name = os.environ.get("MYCLAW_PROVIDER", "openai")
    model_name = os.environ.get("MYCLAW_MODEL")
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_API_BASE")

    safe_id = safe_session_id(session_id)
    logger = RunLogger(run_id=f"interactive-{safe_id}")
    run_already_exists = logger.path.exists()
    if not run_already_exists:
        logger.log_event(
            "interactive_session_started",
            session_id=safe_id,
            provider=provider_name,
            model=model_name,
        )

    transcript = load_transcript(safe_id)
    conversation_turn = next_conversation_turn(transcript)

    # Build conversation history
    history = []
    for item in transcript:
        if item["role"] == "user":
            history.append({"type": "human", "content": item["content"]})
        elif item["role"] == "assistant":
            history.append({"type": "ai", "content": item["content"]})

    logger.log_event(
        "user_input",
        session_id=safe_id,
        content_preview=message[:500],
        history_turns=len(history),
        conversation_turn=conversation_turn,
    )

    llm = get_provider(
        provider_name=provider_name,
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )

    harness = create_agent_harness(llm)

    history_msgs = []
    for item in transcript:
        if item["role"] == "user":
            history_msgs.append({"type": "HumanMessage", "content_preview": item["content"]})
        elif item["role"] == "assistant":
            history_msgs.append({"type": "AIMessage", "content_preview": item["content"][:200]})

    logger.log_event(
        "llm_input",
        session_id=safe_id,
        conversation_turn=conversation_turn,
        react_step=1,
        react_phase="input",
        message_count=len(history_msgs) + 1,
        state_message_count=len(history_msgs),
        has_summary=False,
        message_types=[m["type"] for m in history_msgs] + ["HumanMessage"],
        messages=history_msgs,
    )

    memory_events = load_memory_injection_events()
    if not memory_events:
        logger.log_event(
            "memory_context_empty",
            session_id=safe_id,
            conversation_turn=conversation_turn,
        )
    for memory_event in memory_events:
        logger.log_event(
            "memory_injected",
            session_id=safe_id,
            conversation_turn=conversation_turn,
            **memory_event,
        )

    write_checkpoint(
        safe_id,
        status="llm_calling",
        conversation_turn=conversation_turn,
        run_id=logger.run_id,
    )
    try:
        result = harness.run(message, verbose=False, history=transcript)
    except Exception as exc:
        write_checkpoint(
            safe_id,
            status="error",
            conversation_turn=conversation_turn,
            run_id=logger.run_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        append_session_event(
            safe_id,
            "turn_error",
            conversation_turn=conversation_turn,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise

    answer = result["answer"]
    turns = result["turns"]
    state = result["state"]
    gate_events_by_call: dict[str, dict] = {}
    for gate_event in result.get("tool_gate_events", []):
        key = str(gate_event.get("tool_call_id") or "")
        if key:
            gate_events_by_call[key] = gate_event
    hook_events = list(result.get("hook_events", []))
    context_guard_events = list(result.get("context_guard_events", []))
    memory_candidate_events = list(result.get("memory_candidate_events", []))
    for context_event in context_guard_events:
        logger.log_event(
            "context_guard",
            session_id=safe_id,
            conversation_turn=conversation_turn,
            **context_event,
        )
        append_session_event(
            safe_id,
            "context_guard",
            conversation_turn=conversation_turn,
            **context_event,
        )

    for candidate_event in memory_candidate_events:
        logger.log_event(
            "memory_candidate_signal",
            session_id=safe_id,
            conversation_turn=conversation_turn,
            react_step=max(1, turns),
            **candidate_event,
        )
        append_session_event(
            safe_id,
            "memory_candidate_signal",
            conversation_turn=conversation_turn,
            **candidate_event,
        )

    current_react_step = 1
    logged_input_steps = {1}
    for msg in state.messages:
        if msg.role == "assistant" and msg.tool_calls:
            for tc in msg.tool_calls:
                gate_event = gate_events_by_call.get(str(tc.get("id") or ""))
                logger.log_event(
                    "tool_call",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    react_step=current_react_step,
                    react_phase="action",
                    tool_name=tc.get("name"),
                    tool_args=tc.get("args", {}),
                    tool_call_id=tc.get("id"),
                )
                append_session_event(
                    safe_id,
                    "tool_call",
                    conversation_turn=conversation_turn,
                    react_step=current_react_step,
                    tool_name=tc.get("name"),
                    tool_args=tc.get("args", {}),
                    tool_call_id=tc.get("id"),
                )
                if gate_event:
                    logger.log_event(
                        "tool_gate_decision",
                        session_id=safe_id,
                        conversation_turn=conversation_turn,
                        react_step=current_react_step,
                        react_phase="policy",
                        tool_name=tc.get("name"),
                        tool_args=tc.get("args", {}),
                        tool_call_id=tc.get("id"),
                        tool_gate_decision=gate_event.get("decision"),
                        permission=gate_event.get("permission"),
                        resource=gate_event.get("resource"),
                        action=gate_event.get("action"),
                        scope=gate_event.get("scope"),
                        risk=gate_event.get("risk"),
                        requires_consent=gate_event.get("requires_consent"),
                        reason=gate_event.get("reason"),
                        policy_mode=gate_event.get("mode"),
                        memory_scope=gate_event.get("memory_scope"),
                        memory_scope_confidence=gate_event.get("memory_scope_confidence"),
                        memory_scope_reason=gate_event.get("memory_scope_reason"),
                        source_route=gate_event.get("source_route"),
                        source_route_confidence=gate_event.get("source_route_confidence"),
                        source_route_reason=gate_event.get("source_route_reason"),
                    )
        elif msg.role == "tool":
            metadata = msg.metadata or {}
            logger.log_event(
                "tool_result",
                session_id=safe_id,
                conversation_turn=conversation_turn,
                react_step=current_react_step,
                react_phase="observation",
                tool_name=msg.name,
                tool_result=msg.content[:500] if msg.content else "",
                tool_call_id=msg.tool_call_id,
                tool_ok=metadata.get("tool_ok"),
                tool_status=metadata.get("tool_status"),
                tool_metadata=metadata.get("tool_metadata"),
            )
            append_session_event(
                safe_id,
                "tool_result",
                conversation_turn=conversation_turn,
                react_step=current_react_step,
                tool_name=msg.name,
                tool_result=msg.content[:500] if msg.content else "",
                tool_call_id=msg.tool_call_id,
                tool_ok=metadata.get("tool_ok"),
                tool_status=metadata.get("tool_status"),
                tool_metadata=metadata.get("tool_metadata"),
            )
        elif msg.role == "assistant":
            final_react_step = max(1, turns)
            if final_react_step not in logged_input_steps:
                logger.log_event(
                    "llm_input",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    react_step=final_react_step,
                    react_phase="input",
                    message_count=len(history_msgs) + final_react_step,
                    state_message_count=len(history_msgs) + final_react_step - 1,
                    has_summary=False,
                    message_types=[],
                    messages=[],
                )
                logged_input_steps.add(final_react_step)
        if msg.role == "tool":
            current_react_step += 1
            if current_react_step <= turns and current_react_step not in logged_input_steps:
                logger.log_event(
                    "llm_input",
                    session_id=safe_id,
                    conversation_turn=conversation_turn,
                    react_step=current_react_step,
                    react_phase="input",
                    message_count=len(history_msgs) + current_react_step,
                    state_message_count=len(history_msgs) + current_react_step - 1,
                    has_summary=False,
                    message_types=[],
                    messages=[],
                )
                logged_input_steps.add(current_react_step)

    logger.log_event(
        "ai_message",
        session_id=safe_id,
        conversation_turn=conversation_turn,
        react_step=max(1, turns),
        react_phase="final",
        content=answer,
        content_preview=answer[:500],
    )
    append_session_event(
        safe_id,
        "ai_message",
        conversation_turn=conversation_turn,
        content=answer,
        content_preview=answer[:500],
    )
    for hook_event in hook_events:
        logger.log_event(
            "agent_hook",
            session_id=safe_id,
            conversation_turn=conversation_turn,
            react_step=max(1, turns),
            **hook_event,
        )

    transcript.append({"role": "user", "content": message})
    transcript.append({"role": "assistant", "content": answer})
    save_transcript(safe_id, transcript)

    logger.log_event(
        "turn_completed",
        session_id=safe_id,
        conversation_turn=conversation_turn,
        react_step=max(1, turns),
        react_phase="completed",
        harness_turns=turns,
        state_message_count=len(history_msgs) + 2,
        has_summary=False,
        answer_preview=answer[:800],
    )
    append_session_event(
        safe_id,
        "turn_completed",
        conversation_turn=conversation_turn,
        harness_turns=turns,
        answer_preview=answer[:800],
    )
    clear_checkpoint(safe_id)

    return {
        "session_id": safe_id,
        "run_id": logger.run_id,
        "run_path": str(logger.path),
        "answer": answer,
        "turns": turns,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--stream", action="store_true", help="Enable streaming mode (JSONL output)")
    args = parser.parse_args()

    try:
        if args.stream:
            run_turn_stream(session_id=args.session_id, message=args.message)
        else:
            result = run_turn(session_id=args.session_id, message=args.message)
            print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
