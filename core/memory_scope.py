"""Lightweight memory scope classifier.

This is not meant to be final intelligence. It gives the harness a structured
place to record why a memory write looks like session memory, long-term profile,
or project knowledge, so we can iterate with evals instead of adding more prompt
text.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryScopeDecision:
    scope: str
    confidence: float
    reason: str
    intent: str = "none"
    persistence: str = "none"
    subject: str = "unknown"
    signals: tuple[str, ...] = ()

    def to_trace(self) -> dict[str, object]:
        return {
            "memory_scope": self.scope,
            "memory_scope_confidence": round(self.confidence, 3),
            "memory_scope_reason": self.reason,
            "memory_intent": self.intent,
            "memory_persistence": self.persistence,
            "memory_subject": self.subject,
            "memory_signals": list(self.signals),
        }


def infer_memory_scope(user_input: str, tool_name: str) -> MemoryScopeDecision:
    text = user_input.lower()
    original = user_input

    transient_markers = ["临时", "当前会话", "这次会话", "本轮", "本次", "这次讨论", "先暂时", "现在先", "不要长期保存", "不要记忆", "temporary"]
    profile_markers = ["以后", "我喜欢", "我更喜欢", "我偏好", "我习惯", "我的偏好", "个人偏好", "回答风格", "请记住", "记住：", "偏好"]
    note_markers = ["badcase", "项目", "设计", "规范", "记录", "文档", "方案", "计划", "总结"]
    write_markers = ["记住", "记录", "保存", "写入", "以后", "总结一下", "整理", "我喜欢", "我更喜欢", "我偏好", "我习惯"]
    update_markers = ["更新", "修改", "补充", "修正", "改成", "改掉", "追加", "删除", "移除"]

    def matched(markers: list[str]) -> tuple[str, ...]:
        return tuple(marker for marker in markers if marker.lower() in text or marker in original)

    transient_hits = matched(transient_markers)
    profile_hits = matched(profile_markers)
    note_hits = matched(note_markers)
    update_hits = matched(update_markers)
    write_hits = matched(write_markers)
    intent = "update" if update_hits else "write" if write_hits or profile_hits else "none"

    if transient_hits:
        return MemoryScopeDecision(
            "session",
            0.82,
            "用户表达了临时或当前会话范围",
            intent=intent,
            persistence="current_session",
            subject="conversation",
            signals=transient_hits,
        )

    if tool_name == "save_user_profile":
        if profile_hits:
            return MemoryScopeDecision(
                "profile",
                0.78,
                "用户表达了长期偏好、个人画像或明确记住",
                intent=intent if intent != "none" else "write",
                persistence="cross_session",
                subject="user_profile",
                signals=profile_hits,
            )
        return MemoryScopeDecision(
            "profile",
            0.55,
            "工具目标是用户画像，但用户语义不够明确",
            intent=intent,
            persistence="cross_session",
            subject="user_profile",
        )

    if tool_name == "save_note":
        if note_hits:
            return MemoryScopeDecision(
                "note",
                0.74,
                "用户内容更像项目知识、记录或可检索笔记",
                intent=intent if intent != "none" else "write",
                persistence="searchable",
                subject="project_or_note",
                signals=note_hits,
            )
        return MemoryScopeDecision(
            "note",
            0.55,
            "工具目标是笔记，但用户语义不够明确",
            intent=intent,
            persistence="searchable",
            subject="project_or_note",
        )

    return MemoryScopeDecision("none", 0.0, "不是记忆写入工具")
