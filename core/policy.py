"""Tool permission policy and hook primitives for myClaw.

The policy layer is intentionally resource/action based. It avoids baking
case-specific prompts into the harness and gives later iterations one place to
replace simple rules with richer intent classifiers or user confirmation UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
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


class ToolPolicy:
    """Resource/action permission map for tool calls.

    `off` keeps behavior unchanged. `monitor` records structured decisions
    without blocking execution. `enforce` turns
    consent-requiring actions into ASK unless the caller supplies an explicit
    `_permission_grant` argument. This lets the harness evolve toward real user
    approval without changing every tool wrapper.
    """

    def __init__(self, mode: str | None = None) -> None:
        config = load_policy_config()
        self.mode = (mode or os.environ.get("MYCLAW_POLICY_MODE") or str(config.get("mode", "off"))).strip().lower()
        if self.mode not in {"off", "monitor", "enforce"}:
            self.mode = "off"

    def evaluate(self, context: ToolGateContext) -> ToolGateResult:
        permission = tool_permission_for(context.tool_name)
        explicit_grant = str(context.args.get("_permission_grant", "")).lower() in {"true", "yes", "allow"}
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
            context.tool_name in {"save_user_profile", "save_note"}
            and memory_scope.scope == "session"
            and memory_scope.confidence >= 0.65
        ):
            reasons.append("临时或当前会话信息禁止写入长期记忆")
            return ToolGateResult(
                decision=ToolGateDecision.DENY,
                permission=permission,
                reason="；".join(reasons),
                mode=self.mode,
                metadata=metadata,
            )
        if (
            context.tool_name in {"save_user_profile", "save_note"}
            and _contains_sensitive_memory(str(context.user_input), context.args)
        ):
            reasons.append("银行卡密码、密码、secret、token、API key 等敏感凭据禁止写入长期记忆")
            return ToolGateResult(
                decision=ToolGateDecision.DENY,
                permission=permission,
                reason="；".join(reasons),
                mode=self.mode,
                metadata={**metadata, "sensitive_memory": True},
            )

        if self.mode == "off":
            return ToolGateResult(
                decision=ToolGateDecision.ALLOW,
                permission=permission,
                reason="权限检查关闭，工具直接放行",
                mode=self.mode,
                metadata=metadata,
            )

        needs_confirmation = permission.requires_consent
        if (
            context.tool_name in {"web_search", "read_url"}
            and source_route.route == "local_first"
            and source_route.confidence >= 0.6
        ):
            needs_confirmation = True
            reasons.append("这次联网调用看起来应先走本地项目/会话来源")

        if self.mode == "enforce" and needs_confirmation and not explicit_grant:
            return ToolGateResult(
                decision=ToolGateDecision.ASK,
                permission=permission,
                reason="；".join(reasons) or "该工具需要用户确认后再执行",
                mode=self.mode,
                metadata=metadata,
            )

        return ToolGateResult(
            decision=ToolGateDecision.ALLOW,
            permission=permission,
            reason="；".join(reasons) or "当前权限配置允许执行",
            mode=self.mode,
            metadata=metadata,
        )


def tool_permission_for(tool_name: str) -> ToolPermission:
    permissions: dict[str, ToolPermission] = {
        "save_note": ToolPermission("memory.note", "write", risk="medium", requires_consent=True),
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


def _contains_sensitive_memory(user_input: str, args: dict[str, Any]) -> bool:
    text = f"{user_input}\n{args.get('new_content', '')}\n{args.get('content', '')}".lower()
    markers = ["银行卡密码", "密码", "secret", "token", "api key", "apikey", "私钥", "密钥", "credential"]
    return any(marker in text for marker in markers)
