"""Agent state definitions for myClaw - Custom implementation."""

from dataclasses import dataclass, field
from typing import Any, Literal
from datetime import datetime


# Context trimming thresholds
CONTEXT_TRIM_TRIGGER = 40   # When total messages exceed this, trigger trimming
CONTEXT_TRIM_KEEP = 10      # How many recent turns to keep after trimming


@dataclass
class Message:
    """Standardized message format - '对内丰富，对外兼容' design.

    Attributes:
        role: Message role - "user", "assistant", "system", "tool"
        content: The message content.
        timestamp: Unix timestamp when message was created.
        metadata: Extra data for logging and future extensions.
        tool_calls: For assistant messages - list of tool calls to make.
        tool_call_id: For tool messages - ID linking to the tool call that produced this result.
        name: For tool messages - name of the tool that was called.
    """
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None  # For tool messages - the tool name

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAI API compatible format.

        Returns:
            Dict with 'role', 'content', and optionally 'tool_calls' or 'tool_call_id'.
        """
        result = {
            "role": self.role,
            "content": self.content,
        }

        if self.role == "assistant" and self.tool_calls:
            result["tool_calls"] = self.tool_calls

        if self.role == "tool":
            result["tool_call_id"] = self.tool_call_id
            result["name"] = self.name

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create Message from a dict (e.g., loaded from JSON)."""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", datetime.now().timestamp()),
            metadata=data.get("metadata", {}),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
        )


@dataclass
class AgentState:
    """The state of the agent - simple Python dataclass, no LangGraph deps.

    Attributes:
        messages: List of conversation messages.
        summary: Compressed summary of older messages for context efficiency.
        tool_results: List of recent tool results for ReAct observation.
    """

    messages: list[Message] = field(default_factory=list)
    summary: str = ""
    tool_results: list[dict[str, Any]] = field(default_factory=list)

    def add_user_message(self, content: str) -> None:
        """Add a human user message."""
        self.messages.append(Message(role="user", content=content))

    def add_ai_message(self, content: str, tool_calls: list[dict[str, Any]] | None = None) -> None:
        """Add an AI assistant message."""
        self.messages.append(Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        ))

    def add_tool_message(
        self,
        name: str,
        content: str,
        tool_call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a tool result message."""
        self.messages.append(Message(
            role="tool",
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            metadata=metadata or {},
        ))
        self.tool_results.append({"tool_name": name, "content": content, "metadata": metadata or {}})

    def add_system_message(self, content: str) -> None:
        """Add a system message."""
        self.messages.append(Message(role="system", content=content))

    def get_messages_for_llm(self) -> list[dict[str, Any]]:
        """Get all messages in OpenAI API compatible format for LLM input."""
        return [msg.to_dict() for msg in self.messages]

    def get_recent_tool_results(self) -> list[dict[str, Any]]:
        """Get recent tool results for ReAct observation."""
        return self.tool_results[-5:] if self.tool_results else []

    def count_turns(self) -> int:
        """Count number of turns (each user message = 1 turn)."""
        return sum(1 for msg in self.messages if msg.role == "user")

    def trim_context(self) -> str:
        """Trim old messages to prevent token overflow.

        When message count exceeds CONTEXT_TRIM_TRIGGER, keeps the last
        CONTEXT_TRIM_KEEP turns and summarizes older content into a summary.

        Returns:
            The generated summary string of trimmed content.
        """
        total_msgs = len(self.messages)
        if total_msgs <= CONTEXT_TRIM_TRIGGER:
            return ""  # No trimming needed

        # Separate messages by role for analysis
        user_msgs = [(i, m) for i, m in enumerate(self.messages) if m.role == "user"]
        ai_msgs = [(i, m) for i, m in enumerate(self.messages) if m.role == "assistant"]
        tool_msgs = [(i, m) for i, m in enumerate(self.messages) if m.role == "tool"]

        if len(user_msgs) <= CONTEXT_TRIM_KEEP:
            return ""  # Already have few enough turns

        # Calculate how many to keep
        to_keep = CONTEXT_TRIM_KEEP
        keep_start_idx = user_msgs[-to_keep][0] if user_msgs else 0

        # Build summary of old messages
        old_msgs = self.messages[:keep_start_idx]
        summary_parts = []
        for msg in old_msgs:
            if msg.role == "user":
                content = msg.content[:100] + ("..." if len(msg.content) > 100 else "")
                summary_parts.append(f"User: {content}")
            elif msg.role == "assistant":
                # Skip very long assistant messages in summary
                content = msg.content[:150] + ("..." if len(msg.content) > 150 else "")
                summary_parts.append(f"Assistant: {content}")
            # Skip tool messages in summary for brevity

        summary_text = "; ".join(summary_parts[:20])  # Limit summary length
        old_turn_count = sum(1 for m in old_msgs if m.role == "user")

        # Keep only messages from keep_start_idx onwards
        self.messages = self.messages[keep_start_idx:]
        self.tool_results = []  # Reset tool results after trim

        # Update summary
        self.summary = f"[Earlier conversation ({old_turn_count} turns): {summary_text}]"

        return self.summary
