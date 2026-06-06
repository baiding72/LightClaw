"""Lightweight implicit-memory candidate signals.

These events are observational only. They help us see stable preference
patterns in trace logs without writing to long-term profile memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TRANSIENT_MARKERS = ("临时", "本轮", "本次", "当前会话", "这次会话", "不要记忆", "不要长期保存", "先暂时")
SENSITIVE_MARKERS = ("密码", "secret", "token", "api key", "apikey", "私钥", "密钥", "银行卡密码", "credential")


@dataclass(frozen=True)
class MemoryCandidateSignal:
    key: str
    label: str
    evidence: str
    confidence: float
    evidence_count: int
    threshold: int = 3
    persisted: bool = False
    would_prompt_for_confirmation: bool = False
    suppressed: bool = False
    suppression_reason: str = ""

    def to_trace(self) -> dict[str, Any]:
        return {
            "candidate_key": self.key,
            "candidate_label": self.label,
            "candidate_evidence": self.evidence[:300],
            "candidate_confidence": round(self.confidence, 3),
            "candidate_evidence_count": self.evidence_count,
            "candidate_threshold": self.threshold,
            "candidate_persisted": self.persisted,
            "would_prompt_for_confirmation": self.would_prompt_for_confirmation,
            "suppressed": self.suppressed,
            "suppression_reason": self.suppression_reason,
        }


RULES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "answer_style.concise",
        "用户可能偏好简短直接的回答",
        ("短一点", "简洁", "简短", "直接一点", "别太长", "不用展开", "少废话"),
        ("不要简洁", "不用简洁", "详细一点", "展开讲", "多解释"),
    ),
    (
        "language.zh",
        "用户可能偏好中文回答",
        ("用中文", "中文回答", "说中文", "以后中文", "请用中文"),
        ("不用中文", "用英文", "英文回答", "以后英文"),
    ),
    (
        "workflow.test_first",
        "用户可能偏好先验证再总结",
        ("先跑测试", "先测试", "跑完测试", "验证后", "先验证"),
        ("不用测试", "不要跑测试", "先别测试"),
    ),
    (
        "answer_structure.conclusion_first",
        "用户可能偏好先给结论再解释",
        ("先给结论", "结论先行", "先说结论", "先结论"),
        ("不要先给结论", "别先说结论"),
    ),
)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def _user_messages(history: list[dict[str, str]] | None, current: str) -> list[str]:
    messages = [
        str(item.get("content", ""))
        for item in history or []
        if item.get("role") == "user" and str(item.get("content", "")).strip()
    ]
    messages.append(current)
    return messages


def extract_memory_candidate_signals(
    user_input: str,
    history: list[dict[str, str]] | None = None,
    *,
    threshold: int = 3,
) -> list[MemoryCandidateSignal]:
    """Extract trace-only preference candidates from user text and session history."""
    text = user_input.strip()
    if not text:
        return []

    suppressed_reason = ""
    if _contains_any(text, TRANSIENT_MARKERS):
        suppressed_reason = "transient_scope"
    elif _contains_any(text, SENSITIVE_MARKERS):
        suppressed_reason = "sensitive_content"

    user_messages = _user_messages(history, text)
    signals: list[MemoryCandidateSignal] = []
    for key, label, positive_markers, negative_markers in RULES:
        current_positive = _contains_any(text, positive_markers)
        current_negative = _contains_any(text, negative_markers)
        if not current_positive and not current_negative:
            continue

        evidence_count = sum(1 for message in user_messages if _contains_any(message, positive_markers))
        suppression = suppressed_reason
        if current_negative:
            suppression = "reverse_preference"
        signals.append(
            MemoryCandidateSignal(
                key=key,
                label=label,
                evidence=text,
                confidence=0.72 if current_positive else 0.5,
                evidence_count=evidence_count,
                threshold=threshold,
                would_prompt_for_confirmation=bool(current_positive and evidence_count >= threshold and not suppression),
                suppressed=bool(suppression),
                suppression_reason=suppression,
            )
        )
    return signals
