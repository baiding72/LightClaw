"""Tool permission policy and hook primitives for myClaw.

The policy layer turns model tool intent into an explicit permission decision
before any handler runs. Its core pipeline follows:

1. deny rules
2. mode check
3. allow rules
4. ask user
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import fnmatch
import os
import re
from typing import Any

from core.config import load_policy_config
from core.memory_scope import infer_memory_scope
from core.source_routing import infer_source_route


class ToolGateDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass(frozen=True)
class ToolPermission:
    resource: str
    action: str
    scope: str = "local"
    risk: str = "low"
    requires_consent: bool = False

    @property
    def key(self) -> str:
        return f"{self.resource}:{self.action}"


@dataclass(frozen=True)
class ToolGateContext:
    tool_name: str
    args: dict[str, Any]
    user_input: str = ""
    session_id: str | None = None
    react_step: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolGateResult:
    decision: ToolGateDecision
    permission: ToolPermission
    reason: str
    mode: str = "off"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_trace(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "permission": self.permission.key,
            "resource": self.permission.resource,
            "action": self.permission.action,
            "scope": self.permission.scope,
            "risk": self.permission.risk,
            "requires_consent": self.permission.requires_consent,
            "reason": self.reason,
            "mode": self.mode,
            **self.metadata,
        }


@dataclass(frozen=True)
class PermissionRule:
    """Small permission clause matched against a tool call."""

    tool: str
    behavior: ToolGateDecision
    reason: str
    path: str | None = None
    content: str | None = None
    arg: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches(self, context: ToolGateContext) -> bool:
        if not fnmatch.fnmatch(context.tool_name, self.tool):
            return False
        if self.path is not None and not _path_matches(self.path, context):
            return False
        if self.content is not None and not _content_matches(self.content, context, self.arg):
            return False
        return True


READ_ONLY_TOOLS = {
    "calculator",
    "echo",
    "get_system_info",
    "get_time",
    "check_office_dir",
    "list_office_files",
    "list_tasks",
    "read_office_file",
    "read_note",
    "read_user_profile",
    "search_notes",
}
WRITE_TOOLS = {
    "cancel_task",
    "execute_office_shell",
    "modify_task",
    "save_note",
    "save_user_profile",
    "schedule_task",
    "update_office_file",
    "write_office_file",
}
NETWORK_TOOLS = {"web_search", "read_url"}
SHELL_TOOLS = {"execute_office_shell"}


class ToolPolicy:
    """Rule-based permission map for tool calls.

    Supported modes:
    - off: bypass normal policy tracing/blocking, except hard safety denials.
    - default: ask for gray-area or consent-requiring actions.
    - plan: allow reads, deny writes and network.
    - auto: allow low-risk and read-only calls, ask for risky actions.

    Backward compatibility:
    - monitor behaves like auto but still emits gate traces.
    - enforce behaves like default.
    """

    def __init__(
        self,
        mode: str | None = None,
        deny_rules: list[PermissionRule] | None = None,
        allow_rules: list[PermissionRule] | None = None,
    ) -> None:
        config = load_policy_config()
        raw_mode = mode or os.environ.get("MYCLAW_POLICY_MODE") or str(config.get("mode", "off"))
        self.mode = _normalize_mode(raw_mode)
        self.deny_rules = list(deny_rules) if deny_rules is not None else _default_deny_rules()
        self.allow_rules = list(allow_rules) if allow_rules is not None else _default_allow_rules()
        self.denied_count = 0

    def evaluate(self, context: ToolGateContext) -> ToolGateResult:
        permission = tool_permission_for(context.tool_name)
        metadata, reasons = _context_metadata(context)

        hard_deny = _hard_memory_denial(context, permission, metadata, reasons, self.mode)
        if hard_deny:
            self._record_denial(hard_deny)
            return hard_deny

        matched_deny = self._match_rules(self.deny_rules, context)
        if matched_deny:
            result = self._result(
                matched_deny.behavior,
                permission,
                _with_reasons(reasons, matched_deny.reason),
                {**metadata, **matched_deny.metadata, "matched_rule": "deny"},
            )
            self._record_denial(result)
            return result

        if self.mode == "off":
            return self._result(
                ToolGateDecision.ALLOW,
                permission,
                "权限检查关闭，工具直接放行",
                metadata,
            )

        mode_result = self._mode_check(context, permission, metadata, reasons)
        if mode_result:
            self._record_denial(mode_result)
            return mode_result

        matched_allow = self._match_rules(self.allow_rules, context)
        if matched_allow:
            return self._result(
                matched_allow.behavior,
                permission,
                _with_reasons(reasons, matched_allow.reason),
                {**metadata, **matched_allow.metadata, "matched_rule": "allow"},
            )

        decision = ToolGateDecision.ASK
        explicit_grant = _has_explicit_grant(context)
        if explicit_grant:
            decision = ToolGateDecision.ALLOW
        result = self._result(
            decision,
            permission,
            _with_reasons(reasons, "未命中 allow 规则，需要用户确认"),
            metadata,
        )
        self._record_denial(result)
        return result

    def _mode_check(
        self,
        context: ToolGateContext,
        permission: ToolPermission,
        metadata: dict[str, Any],
        reasons: list[str],
    ) -> ToolGateResult | None:
        if self.mode == "plan":
            if context.tool_name in WRITE_TOOLS:
                return self._result(
                    ToolGateDecision.DENY,
                    permission,
                    _with_reasons(reasons, "plan 模式只允许读，不允许写入或修改"),
                    metadata,
                )
            if context.tool_name in NETWORK_TOOLS:
                return self._result(
                    ToolGateDecision.DENY,
                    permission,
                    _with_reasons(reasons, "plan 模式不自动联网"),
                    metadata,
                )

        if self.mode == "auto":
            if context.tool_name in READ_ONLY_TOOLS:
                return self._result(
                    ToolGateDecision.ALLOW,
                    permission,
                    _with_reasons(reasons, "auto 模式自动放行只读工具"),
                    metadata,
                )
            if _has_explicit_grant(context):
                return self._result(
                    ToolGateDecision.ALLOW,
                    permission,
                    _with_reasons(reasons, "调用参数包含显式权限授权"),
                    metadata,
                )
            if permission.requires_consent or permission.risk in {"medium", "high"}:
                return self._result(
                    ToolGateDecision.ASK,
                    permission,
                    _with_reasons(reasons, "auto 模式下中高风险工具仍需确认"),
                    metadata,
                )

        if self.mode == "default":
            if _has_explicit_grant(context):
                return self._result(
                    ToolGateDecision.ALLOW,
                    permission,
                    _with_reasons(reasons, "调用参数包含显式权限授权"),
                    metadata,
                )
            if permission.requires_consent:
                return self._result(
                    ToolGateDecision.ASK,
                    permission,
                    _with_reasons(reasons, "该工具需要用户确认后再执行"),
                    metadata,
                )

        return None

    def _match_rules(self, rules: list[PermissionRule], context: ToolGateContext) -> PermissionRule | None:
        for rule in rules:
            if rule.matches(context):
                return rule
        return None

    def _result(
        self,
        decision: ToolGateDecision,
        permission: ToolPermission,
        reason: str,
        metadata: dict[str, Any],
    ) -> ToolGateResult:
        if self.denied_count and decision != ToolGateDecision.ALLOW:
            metadata = {**metadata, "denied_count": self.denied_count}
        return ToolGateResult(
            decision=decision,
            permission=permission,
            reason=reason,
            mode=self.mode,
            metadata=metadata,
        )

    def _record_denial(self, result: ToolGateResult) -> None:
        if result.decision == ToolGateDecision.DENY:
            self.denied_count += 1


def tool_permission_for(tool_name: str) -> ToolPermission:
    permissions: dict[str, ToolPermission] = {
        "cancel_task": ToolPermission("task", "cancel", risk="medium", requires_consent=True),
        "check_office_dir": ToolPermission("office.shell", "inspect"),
        "execute_office_shell": ToolPermission("office.shell", "execute", risk="high", requires_consent=True),
        "list_tasks": ToolPermission("task", "list"),
        "modify_task": ToolPermission("task", "update", risk="medium", requires_consent=True),
        "save_note": ToolPermission("memory.note", "write", risk="medium", requires_consent=True),
        "schedule_task": ToolPermission("task", "create", risk="medium", requires_consent=True),
        "search_notes": ToolPermission("memory.note", "search"),
        "read_note": ToolPermission("memory.note", "read"),
        "save_user_profile": ToolPermission("memory.profile", "write", risk="high", requires_consent=True),
        "read_user_profile": ToolPermission("memory.profile", "read"),
        "write_office_file": ToolPermission("office.file", "create", risk="medium", requires_consent=True),
        "update_office_file": ToolPermission("office.file", "update", risk="medium", requires_consent=True),
        "read_office_file": ToolPermission("office.file", "read"),
        "list_office_files": ToolPermission("office.file", "list"),
        "web_search": ToolPermission("external.web", "search", scope="network", risk="medium", requires_consent=True),
        "read_url": ToolPermission("external.web", "read", scope="network", risk="medium", requires_consent=True),
    }
    return permissions.get(tool_name, ToolPermission("tool", "execute"))


def _default_deny_rules() -> list[PermissionRule]:
    return [
        PermissionRule("*", ToolGateDecision.DENY, "文件路径不能越过 office sandbox", path="../*"),
        PermissionRule("*", ToolGateDecision.DENY, "文件路径不能使用绝对路径", path="/*"),
        PermissionRule("*", ToolGateDecision.DENY, "文件路径不能使用 home 目录", path="~*"),
        PermissionRule("execute_office_shell", ToolGateDecision.DENY, "shell 命令包含危险执行片段", content="dangerous_shell"),
    ]


def _default_allow_rules() -> list[PermissionRule]:
    return [
        PermissionRule("get_time", ToolGateDecision.ALLOW, "命中只读工具 allow 规则"),
        PermissionRule("calculator", ToolGateDecision.ALLOW, "命中只读工具 allow 规则"),
        PermissionRule("echo", ToolGateDecision.ALLOW, "命中只读工具 allow 规则"),
        PermissionRule("get_system_info", ToolGateDecision.ALLOW, "命中只读工具 allow 规则"),
        PermissionRule("check_office_dir", ToolGateDecision.ALLOW, "命中 office 只读 allow 规则"),
        PermissionRule("list_office_files", ToolGateDecision.ALLOW, "命中 office 只读 allow 规则"),
        PermissionRule("read_office_file", ToolGateDecision.ALLOW, "命中 office 只读 allow 规则"),
        PermissionRule("search_notes", ToolGateDecision.ALLOW, "命中 memory 只读 allow 规则"),
        PermissionRule("read_note", ToolGateDecision.ALLOW, "命中 memory 只读 allow 规则"),
        PermissionRule("read_user_profile", ToolGateDecision.ALLOW, "命中 memory 只读 allow 规则"),
    ]


def _normalize_mode(mode: str | None) -> str:
    normalized = str(mode or "off").strip().lower()
    aliases = {
        "monitor": "auto",
        "enforce": "default",
        "ask": "default",
        "read_only": "plan",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"off", "default", "plan", "auto"}:
        return "off"
    return normalized


def _context_metadata(context: ToolGateContext) -> tuple[dict[str, Any], list[str]]:
    metadata: dict[str, Any] = {}
    reasons: list[str] = []

    memory_scope = infer_memory_scope(context.user_input, context.tool_name)
    if memory_scope.scope != "none":
        metadata.update(memory_scope.to_trace())
        reasons.append(memory_scope.reason)

    source_route = infer_source_route(context.user_input, context.tool_name)
    if source_route.route != "not_network_tool":
        metadata.update(source_route.to_trace())
        reasons.append(source_route.reason)
        if (
            context.tool_name in NETWORK_TOOLS
            and source_route.route == "local_first"
            and source_route.confidence >= 0.6
        ):
            reasons.append("这次联网调用看起来应先走本地项目/会话来源")

    return metadata, reasons


def _hard_memory_denial(
    context: ToolGateContext,
    permission: ToolPermission,
    metadata: dict[str, Any],
    reasons: list[str],
    mode: str,
) -> ToolGateResult | None:
    memory_scope_name = str(metadata.get("memory_scope", ""))
    memory_confidence = float(metadata.get("memory_scope_confidence", 0) or 0)
    if (
        context.tool_name in {"save_user_profile", "save_note"}
        and memory_scope_name == "session"
        and memory_confidence >= 0.65
    ):
        return ToolGateResult(
            decision=ToolGateDecision.DENY,
            permission=permission,
            reason=_with_reasons(reasons, "临时或当前会话信息禁止写入长期记忆"),
            mode=mode,
            metadata=metadata,
        )
    if (
        context.tool_name in {"save_user_profile", "save_note"}
        and _contains_sensitive_memory(str(context.user_input), context.args)
    ):
        return ToolGateResult(
            decision=ToolGateDecision.DENY,
            permission=permission,
            reason=_with_reasons(reasons, "银行卡密码、密码、secret、token、API key 等敏感凭据禁止写入长期记忆"),
            mode=mode,
            metadata={**metadata, "sensitive_memory": True},
        )
    return None


def _path_matches(pattern: str, context: ToolGateContext) -> bool:
    candidates = [
        str(context.args.get("relative_path", "")),
        str(context.args.get("path", "")),
        str(context.args.get("file_path", "")),
    ]
    return any(value and fnmatch.fnmatch(value.strip(), pattern) for value in candidates)


def _content_matches(pattern: str, context: ToolGateContext, arg: str | None = None) -> bool:
    if pattern == "dangerous_shell":
        command = str(context.args.get("command", ""))
        return _dangerous_shell_reason(command) is not None
    values = [str(context.args.get(arg, ""))] if arg else [str(value) for value in context.args.values()]
    return any(fnmatch.fnmatch(value, pattern) for value in values)


def _dangerous_shell_reason(command: str) -> str | None:
    blocked_regexes = [
        r"(?i)(^|\s)sudo(\s|$)",
        r"(?i)(^|\s)su(\s|$)",
        r"(?i)\brm\s+-[^\n]*r[^\n]*f|\brm\s+-[^\n]*f[^\n]*r",
        r"`[^`]+`",
        r"\$\([^)]*\)",
        r">\s*/|>>\s*/",
        r"(^|\s)(curl|wget)\s+[^|;&]*(\|\s*(sh|bash)|>\s*[^&|;]+)",
        r"(^|\s)(chmod|chown)\s+",
    ]
    for pattern in blocked_regexes:
        if re.search(pattern, command):
            return pattern
    shell_meta = ("&&", "||", ";", "|")
    if sum(1 for item in shell_meta if item in command) >= 2:
        return "compound shell metacharacters"
    return None


def _contains_sensitive_memory(user_input: str, args: dict[str, Any]) -> bool:
    text = f"{user_input}\n{args.get('new_content', '')}\n{args.get('content', '')}".lower()
    markers = ["银行卡密码", "密码", "secret", "token", "api key", "apikey", "私钥", "密钥", "credential"]
    return any(marker in text for marker in markers)


def _has_explicit_grant(context: ToolGateContext) -> bool:
    return str(context.args.get("_permission_grant", "")).lower() in {"true", "yes", "allow"}


def _with_reasons(existing: list[str], reason: str) -> str:
    parts = [part for part in [*existing, reason] if part]
    return "；".join(dict.fromkeys(parts))
