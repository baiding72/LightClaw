# myClaw 会话管理与上下文保护

## 存储架构

myClaw 采用**纯内存**会话设计，会话数据存储在 `~/.myclaw/sessions/{session_id}/messages.jsonl`。

```
~/.myclaw/
├── profile.md          # 跨会话长期记忆
├── sessions/
│   └── {session_id}/
│       └── messages.jsonl   # 会话消息持久化
└── policy_config.json       # 工具策略配置
```

**与 CyberClaw 的差异**：
- CyberClaw: JSONL 追加写入，每个会话一个 `.jsonl` 文件
- myClaw: 简化版，消息在 REPL 退出时通过 `state.get_messages_for_llm()` 一次性序列化写入

## 数据格式

```python
# core/state.py Message
@dataclass
class Message:
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: float
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None  # tool 消息专用

    def to_dict(self) -> dict:
        """OpenAI API 兼容格式"""
        result = {"role": self.role, "content": self.content}
        if self.role == "assistant" and self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.role == "tool":
            result["tool_call_id"] = self.tool_call_id
            result["name"] = self.name
        return result
```

**消息类型**：
- `user`: 用户输入
- `assistant`: AI 回复（含 tool_calls）
- `tool`: 工具执行结果
- `system`: 系统消息（system prompt / profile / summary）

## 上下文保护策略

### 1. Context Trimming（滑动窗口）

```python
# core/state.py
CONTEXT_TRIM_TRIGGER = 40   # 超过 40 条消息时触发
CONTEXT_TRIM_KEEP = 10      # 保留最近 10 轮

def trim_context(self) -> str:
    # 保留最近 N 轮，其余摘要为一条 system message
    self.summary = f"[Earlier conversation ({old_turn_count} turns): {summary_text}]"
    self.messages = self.messages[keep_start_idx:]
    return self.summary
```

**流程**：
1. 每轮 ReAct 前检查 `len(state.messages) > CONTEXT_TRIM_TRIGGER`
2. 触发时将早期消息压缩为摘要，保留最近 10 轮
3. 摘要作为 system message 注入 `_build_messages()`

### 2. 每轮长期 Profile 注入

```python
# core/agent.py _build_messages()
def _load_user_profile(self) -> str:
    profile_path = Path.home() / ".myclaw" / "profile.md"
    if profile_path.exists():
        return profile_path.read_text(encoding="utf-8").strip()
    return ""
```

每次 `_build_messages()` 都从磁盘读取最新 profile，确保跨会话记忆。

### 3. CyberClaw 三阶段溢出重试 vs myClaw 简化版

| 特性 | CyberClaw | myClaw |
|------|-----------|--------|
| 溢出检测 | `guard_api_call()` 三阶段 | 仅 context trimming |
| 截断策略 | 截断过大 tool result | 无 |
| 压缩策略 | 保留 20% + 摘要 50% | 保留最后 10 轮 |
| Token 估算 | 真实 API 或 `len(text) // 4` | 简单消息计数 |

myClaw 简化了 token 计数，未实现 tool result 截断。

## 会话生命周期

```
REPL 启动
  ↓
load_session(session_id) → 加载 messages.jsonl → AgentState
  ↓
每次 turn:
  _build_messages(state) → 注入 system + profile + summary + messages
  ↓
  LLM.invoke() / LLM.stream()
  ↓
  state.add_*_message() → 更新内存中的 messages
  ↓
  trim_context() 如需
  ↓
REPL 退出
  ↓
save_session(session_id, state.get_messages_for_llm()) → 写入 messages.jsonl
```

## 消息构建顺序

```python
def _build_messages(self, state: AgentState) -> list[dict]:
    messages = []
    messages.append({"role": "system", "content": self.system_prompt})  # 1. system
    profile = self._load_user_profile()
    if profile:
        messages.append({"role": "system", "content": f"[User Profile]\n{profile}"})  # 2. profile
    if state.summary:
        messages.append({"role": "system", "content": state.summary})  # 3. summary
    for msg in state.messages:
        messages.append(msg.to_dict())  # 4. 对话消息
    return messages
```

最终结构：
```
[system prompt, profile, summary, user msg, assistant msg, tool msg, ...]
```

## 与 CyberClaw 对照

| 机制 | CyberClaw | myClaw |
|------|-----------|--------|
| 存储格式 | JSONL 追加 | messages.jsonl 覆盖写入 |
| 索引文件 | sessions.json | 无 |
| 上下文保护 | 三阶段溢出重试 | 滑动窗口 trimming |
| Profile 注入 | 通过 memory_scope | 每轮磁盘读取 |
| 工具结果截断 | 有 | 无 |
| 手动压缩命令 | `/compact` | 无 |
| REPL 命令 | `/new`, `switch`, `/context` | 基础会话命令 |

## 缺陷与待改进

1. **无增量写入**: 每次 REPL 退出覆盖写入，大会话效率低
2. **无 token 估算**: 无法精确判断上下文溢出
3. **无 tool result 截断**: 大的 tool result 可能撑爆上下文
4. **无 session 索引**: 无法快速列举历史会话