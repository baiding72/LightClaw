# myClaw 安全与约束机制

## 概述

myClaw 实现了两层约束体系：

- **硬边界**：代码层面的强制限制，模型无法绕过
- **软约束**：写在 system prompt 和 docstring 中的行为规范，依赖模型自觉遵守

---

## 已实现的硬边界

### 1. Task 文件线程锁 (`threading.Lock()`)

**目的**：防止多个任务同时读写 `tasks.json` 导致文件损坏

**实现**：`myClaw/core/tools/builtins.py`

```python
_TASKS_LOCK = threading.Lock()

def schedule_task(...):
    with _TASKS_LOCK:
        tasks = _load_tasks()
        tasks.append(new_task)
        _save_tasks(tasks)
```

所有 task 操作（schedule_task, list_tasks, cancel_task, modify_task）都用 `_TASKS_LOCK` 保护，确保 read-modify-write 原子性。

**触发条件**：多线程/多进程并发调用 task 工具时

**测试 Case**：
```python
# 10 threads each scheduling 3 tasks concurrently
threads = [threading.Thread(target=concurrent_schedule, args=(t,)) for t in range(10)]
# 验证：tasks.json 仍是有效 JSON，31 个 task 全部正确写入
```

---

### 2. Office 文件沙箱 (`_safe_path`)

**目的**：防止目录遍历攻击，限制文件操作在 `workspace/office/` 目录内

**实现**：`myClaw/core/tools/files.py`

```python
def _safe_path(relative_path: str) -> Path:
    candidate = (OFFICE_DIR / relative_path).resolve()
    office_root = OFFICE_DIR.resolve()
    if candidate != office_root and office_root not in candidate.parents:
        raise ValueError("path escapes the myClaw office sandbox")
    return candidate
```

所有 office 文件工具（list_office_files, read_office_file, write_office_file, update_office_file）都经过 `_safe_path` 校验。

**触发条件**：尝试访问 `../`、`/absolute`、`~/.ssh` 等路径时

**测试 Case**：
```python
# 合法
read_office_file.invoke({"relative_path": "notes/test.txt"})

# 非法 - 被拦截
read_office_file.invoke({"relative_path": "../../etc/passwd"})
# -> Error: path escapes the myClaw office sandbox
```

---

### 3. Shell 执行沙箱（local 默认，docker 可选）

**目的**：限制 shell 命令只能围绕 office 目录工作，降低提权、数据泄露和资源滥用风险

**实现**：`myClaw/core/tools/shell.py`

#### Backend 选择
默认仍然直接在本机执行，兼容现有测试和开发流程：

```bash
MYCLAW_SHELL_BACKEND=local
```

需要更强隔离时切到 Docker：

```bash
MYCLAW_SHELL_BACKEND=docker
MYCLAW_DOCKER_IMAGE=python:3.12-slim
```

Docker backend 会把 `workspace/office/` 挂载到容器 `/workspace`，并默认使用：

```bash
--pull missing
--network none
--read-only
--cap-drop ALL
--security-opt no-new-privileges
--memory 512m
--cpus 1
--pids-limit 128
--tmpfs /tmp:rw,nosuid,nodev,size=64m
```

可选配置：

```bash
MYCLAW_DOCKER_NETWORK=none
MYCLAW_DOCKER_MEMORY=512m
MYCLAW_DOCKER_CPUS=1
MYCLAW_DOCKER_PIDS=128
MYCLAW_DOCKER_PULL=missing
```

#### Layer 1: 工作目录锁定
```python
subprocess.run(command, shell=True, cwd=str(OFFICE_DIR), ...)
```
local backend 下所有命令从 `workspace/office/` 目录启动。Docker backend 下所有命令从容器内 `/workspace` 启动，容器只挂载 office 目录。

#### Layer 2: 逃逸模式正则拦截
```python
_ESCAPE_PATTERNS = [
    r"\.\.",                          # ../ 路径遍历
    r"(?:^|\s|[<>|&;])/",             # /absolute paths
    r"(?:^|\s|[<>|&;])~",             # ~ home directory
    r"(?:^|\s|[<>|&;])\\",             # Windows absolute \
    r"(?i)(?:^|\s|[<>|&;])[a-z]:",    # Windows drive C:
]
```

#### Layer 3: 禁止特权命令
```python
_BLOCKED_COMMANDS = [
    r"^\s*sudo\s",
    r"^\s*su\s",
    r"^\s*chmod\s+777",
    r"^\s*chmod\s+0",
    r"^\s*wget\s+--",
    r"^\s*curl\s+--",
]
```

#### 超时保护
```python
SHELL_TIMEOUT = 60  # seconds
subprocess.run(..., timeout=SHELL_TIMEOUT)
```

**触发条件**：
- 路径逃逸：`ls ../`, `cat /etc/passwd`, `cd ~`
- 特权提升：`sudo rm`, `su root`
- 超时：`sleep 65`

**测试 Case**：
```python
# 合法
execute_office_shell.invoke({"command": "ls -la"})  # cwd = office/

# 非法 - 被拦截
execute_office_shell.invoke({"command": "ls ../"})  # BLOCKED
execute_office_shell.invoke({"command": "sudo whoami"})  # BLOCKED

# 超时测试，local/docker backend 都会套 60s timeout
execute_office_shell.invoke({"command": "sleep 65"})  # 60s timeout kills it
```

---

### 4. Pre-execution 参数校验

**目的**：在工具执行前验证 required params，防止模型调用缺参数的 tool

**实现**：`myClaw/core/agent.py` 的 `_execute_tool`

```python
schema = tool.get_schema()
required = schema.get("parameters", {}).get("required", [])
missing = [p for p in required if p not in args or args[p] is None]
if missing:
    return f"Error: {tool_name}() missing required argument(s): {', '.join(missing)}. Required: {required}", gate
```

**触发条件**：模型调用 tool 时缺少 required 参数

**测试 Case**：
```python
# echo requires 'message' param
harness._execute_tool('echo', {})  # -> Error: echo() missing required argument(s): message
harness._execute_tool('echo', {'message': 'hello'})  # -> "Echo: hello"
```

---

### 5. Task 时间格式与未来时间校验

**目的**：防止模型调度过去的时间或格式错误的时间

**实现**：`myClaw/core/tools/builtins.py`

```python
target_dt = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
if target_dt <= now:
    return f"Error: target_time must be in the future."
```

同样适用于 `modify_task` 的 `new_time`。

**触发条件**：传入过去时间或非 ISO 格式时间

**测试 Case**：
```python
schedule_task.invoke({'target_time': '2020-01-01 12:00:00', 'description': 'past'})
# -> Error: target_time must be in the future

schedule_task.invoke({'target_time': 'invalid-format', 'description': 'test'})
# -> Error: time format must be YYYY-MM-DD HH:MM:SS
```

---

### 6. Calculator 受限 eval

**目的**：防止注入攻击，只允许纯数学表达式计算

**实现**：`myClaw/core/tools/builtins.py`

```python
result = eval(expression, {"__builtins__": {}}, {})
```

`__builtins__` 被清空，无法执行任意代码。

**触发条件**：传入非数学表达式

**测试 Case**：
```python
calculator.invoke({'expression': '1+1'})  # -> "2"
calculator.invoke({'expression': '__import__("os").system("ls")'})  # -> Error
```

---

### 7. Tool Gate 权限层

**目的**：在模型调用工具和工具真正执行之间增加统一控制点，不把所有约束都塞进 system prompt。

**实现**：`myClaw/core/policy.py` + `myClaw/core/agent.py`

```python
gate = self.tool_policy.evaluate(context)
if gate.decision != ToolGateDecision.ALLOW:
    return "Tool execution paused by policy...", gate
```

工具会先映射成资源和动作：

```text
save_user_profile   -> memory.profile:create
update_user_profile -> memory.profile:update
save_note           -> memory.note:create
update_note         -> memory.note:update
web_search          -> external.web:search
search_local_sources -> local.source:search
```

三种模式：

- `off`：不记录、不拦截。
- `monitor`：记录 gate trace，不拦截。
- `enforce`：高风险或不匹配调用进入 ask，等待前端确认。

**测试 Case**：

```python
policy = ToolPolicy(mode="enforce")
result = policy.evaluate(ToolGateContext(tool_name="web_search", args={"query": "myClaw"}))
assert result.decision == ToolGateDecision.ASK
```

---

### 8. Memory Scope 结构化判断

**目的**：区分临时会话记忆、长期用户画像、可检索项目笔记，避免模型把不同作用域混写。

**实现**：`myClaw/core/memory_scope.py`

现在不只输出 `session/profile/note/none`，还会输出：

```text
memory_intent
memory_persistence
memory_subject
memory_signals
```

这些字段会进入 `tool_gate_decision` trace。比如用户说“这是当前会话临时偏好”，模型却要写 `save_user_profile`，`enforce` 模式会要求确认。

**测试 Case**：

```python
decision = infer_memory_scope("这是当前会话的临时偏好", "save_user_profile")
assert decision.scope == "session"
assert decision.persistence == "current_session"
```

---

### 9. Source Routing + 本地检索

**目的**：让 agent 判断“该查本地还是联网”，并且本地优先不是空口号，而是能真的检索本地资料。

**实现**：

- `myClaw/core/source_routing.py`
- `myClaw/core/local_retrieval.py`
- `myClaw/core/tools/local.py`

本地检索会搜索：

```text
~/.myclaw/profile.md
~/.myclaw/notes/*.json
workspace/office/
myClaw/docs/
runs/*.jsonl
```

当用户问 myClaw、CyberClaw、trace、当前项目、会话历史时，source routing 会倾向 `local_first`，并把 `local_source_hits` 写进 trace。

**测试 Case**：

```python
decision = infer_source_route("myClaw 的 gate policy 是怎么做的", "web_search")
assert decision.route == "local_first"
assert decision.local_hits
```

---

### 10. 记忆写入保护

**目的**：控制 memory 写入的稳定性，减少重复创建、空内容覆盖、长期画像冲突。

**实现**：`myClaw/core/tools/builtins.py`

当前规则：

- `save_note` 只创建新 note，空内容拒绝，重复内容拒绝。
- `update_note` 只更新已有 note，空内容拒绝，内容不变则返回 unchanged。
- `save_user_profile` 只创建不存在的 profile。
- `update_user_profile` 用 merge 追加更新，不默认覆盖。
- profile 出现同名字段不同值时，写入 conflict notice。

**测试 Case**：

```python
save_note.invoke({"content": "同一条项目规范"})
save_note.invoke({"content": " 同一条项目规范 "})
# -> Note already exists

update_user_profile.invoke({"new_content": ""})
# -> Error: user profile update cannot be empty
```

---

## 软约束（写在 prompt/docstring）

### 1. 记忆写入前应先判断作用域

system prompt 要求 notes、profile、office files 不要混用。现在这条已经被 `memory_scope` 和 `ToolPolicy` 部分硬化，但“模型是否主动选择正确工具”仍然是软约束，需要 eval 持续压测。

### 2. 任务调度歧义时间要求追问

`schedule_task` docstring 说：
> 如果用户说"7点"这种歧义时间，应该先追问

但工具只检查时间格式和是否未来，无法判断用户是否表达含糊。

### 3. 删除/修改任务前要求确认

`cancel_task` 和 `modify_task` 的 docstring 要求先列出候选并确认，但工具只按 task_id 操作。

---

## Context Trimming（滑动窗口）

**目的**：防止 token overflow，当对话轮次过多时裁剪旧消息

**实现**：`myClaw/core/state.py`

```python
CONTEXT_TRIM_TRIGGER = 40   # 超过 40 条消息时触发
CONTEXT_TRIM_KEEP = 10      # 保留最近 10 轮

def trim_context(self) -> str:
    # 保留最近 N 轮，其余摘要为一条 system message
    self.summary = f"[Earlier conversation ({old_turn_count} turns): {summary_text}]"
```

`_build_messages` 会在有 summary 时将其注入到 system prompt 中：

```python
if state.summary:
    messages.append({"role": "system", "content": state.summary})
```

**触发条件**：消息数量超过 `CONTEXT_TRIM_TRIGGER`

---

## 每轮长期 Profile 注入

**目的**：让模型知道用户的长期偏好，每次都从磁盘读取最新内容

**实现**：`myClaw/core/agent.py`

```python
def _load_user_profile(self) -> str:
    profile_path = Path.home() / ".myclaw" / "profile.md"
    if profile_path.exists():
        return profile_path.read_text(encoding="utf-8").strip()
    return ""

def _build_messages(self, state):
    profile = self._load_user_profile()
    if profile:
        messages.append({"role": "system", "content": f"[User Profile]\n{profile}"})
```

**触发条件**：每次 `_build_messages` 调用（每轮 ReAct）

---

## 约束与 CyberClaw 对照

| 约束 | CyberClaw | myClaw |
|------|-----------|--------|
| Task 文件线程锁 | ✅ | ✅ 已实现 |
| Office 文件沙箱 | ✅ | ✅ 已实现 |
| Shell 执行沙箱 | ✅ | ✅ 已实现 |
| Pre-execution 参数校验 | ✅ | ✅ 已实现 |
| Task 时间格式校验 | ✅ | ✅ 已实现 |
| Calculator 受限 eval | ✅ | ✅ 已实现 |
| Context trimming | ✅ | ✅ 已实现 |
| 每轮 Profile 注入 | ✅ | ✅ 已实现 |
| Shell 超时 60s | ✅ | ✅ 已实现 |
| Shell 逃逸拦截 | ✅ | ✅ 已实现 |
| Tool Gate 权限层 | ❌ | ✅ 已实现 |
| Memory Scope 结构化判断 | ❌ | ✅ 已实现 |
| Source Routing 本地检索 | ❌ | ✅ 初版已实现 |
| Note/Profile 写入保护 | ⚠️ 主要靠 prompt | ✅ 初版已实现 |
| Skill loader | ✅ | ❌ 未实现 |
| 每轮 Trace 记录 | ✅ | ✅ streaming 模式已完整 |

---

## 测试运行

```bash
# Task 线程锁
cd /Users/baiding/LightClaw
PYTHONPATH=/Users/baiding/LightClaw python -c "
from myClaw.core.tools.builtins import schedule_task, list_tasks, cancel_task
import threading
# 10 threads x 3 tasks = 30 concurrent writes
# 验证 tasks.json 仍是有效 JSON
"

# Office 文件沙箱
PYTHONPATH=/Users/baiding/LightClaw python -c "
from myClaw.core.tools.files import read_office_file
read_office_file.invoke({'relative_path': '../../etc/passwd'})  # BLOCKED
"

# Shell 沙箱
PYTHONPATH=/Users/baiding/LightClaw python -c "
from myClaw.core.tools.shell import execute_office_shell
execute_office_shell.invoke({'command': 'ls ../'})  # BLOCKED
execute_office_shell.invoke({'command': 'sudo rm'})  # BLOCKED
"
```
