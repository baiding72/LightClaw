# LightClaw 项目面试 QA

---

## 项目概览

### 项目定位

个人 AI 助手 harness（agent 运行框架），自己写 ReAct loop，不用 LangGraph，追求轻量可控。

**为什么做这个**：想做个人 AI 助手——能记住我的偏好、能跑定时任务、能调工具。最开始用 LangGraph，但黑盒太多调试不了，后来自己写 ReAct。

**相比 OpenClaw 的优势**：OpenClaw 是通用框架，定制化要翻它的代码，很多我们需要的东西它没有：分层记忆（profile/note）、completion hooks 防说谎、tool gate 门控。LightClaw 定位是轻量、可控、专注个人助手场景。

---

### CyberClaw 项目亮点（来自作者介绍）

**解决的问题**：

1. **黑箱操作**：AI 用了什么工具、传了什么参数、返回了什么结果——完全透明可追溯
2. **安全隐患**：危险命令（删库跑路）没有拦截，风险高
3. **长链路任务**：工具选错了无法回溯，只能一条路走到黑

**CyberClaw 的创新点**：

| 功能             | 说明                                                          |
| -------------- | ----------------------------------------------------------- |
| **Monitor 监控** | 新开终端实时查看工具选择、参数、结果、记忆更新，所有行为可追溯                             |
| **两阶段工具调用**    | 先依据 Description 选工具，看完 Skills.md 再进行一轮决策确认，不合适可以换，准确率提升 40% |
| **双脑记忆**       | 类似 profile/note 分层 + 上下文裁剪                                  |
| **10 个内置工具**   | 即插即用，兼容 OpenClaw 和 Claude Code 的 skills 扩展                  |
| **透明可控**       | 所有 AI 行为可监控、可追溯、可拦截                                         |

**LightClaw 可以借鉴**：

- CyberClaw 的 Monitor 机制——LightClaw 目前只有日志，没有实时监控 UI
- 两阶段决策——LightClaw 的 skill_loader 已经有一阶段（help），可以扩展成两阶段确认
- 工具调用准确率提升 40% 的数据很有说服力

### 整体架构

```
用户输入
  ↓
┌─────────────────────────────────────────────┐
│           AgentHarness (ReAct Loop)          │
│  Think → Act(tool_call) → Observe → Repeat  │
└─────────────────────────────────────────────┘
  ↓
确定性流程（代码控制）：
  1. auto_memory_write  → 自动记忆写入
  2. tool_policy.evaluate() → 工具门控判断
  3. context_guard.protect_state() → 超限压缩
  4. _execute_tool() → 执行工具
  ↓
LLM 决策：
  1. 生成 tool_call（调哪个工具）
  2. 生成 final answer（回复什么）
  3. 决定是否继续循环
  ↓
completion_hook → 检查最终回复
```

### 核心模块

| 模块                   | 文件                 | 作用                              |
| -------------------- | ------------------ | ------------------------------- |
| **ReAct Loop**       | `agent.py`         | AgentHarness 主循环，调度 LLM 和 Tools |
| **Memory Scope**     | `memory_scope.py`  | 判断记忆该存 profile/note/session     |
| **Completion Hooks** | `agent.py`         | 5 个 guard 检测 AI 说谎并替换回复         |
| **Tool Gate**        | `policy.py`        | 工具执行前判断 allow/ask/deny          |
| **Context Guard**    | `context_guard.py` | 工具返回截断 + 消息 trim                |
| **Heartbeat**        | `heartbeat.py`     | 定时任务 producer-consumer          |
| **Skill Loader**     | `skill_loader.py`  | 两阶段懒加载 skill manual             |
| **Checkpoint**       | `checkpoint.py`    | 断点续跑状态持久化                       |
| **Retry**            | `retry.py`         | LLM/provider 层瞬时错误重试            |
| **Tool Schema**      | `tools/base.py`    | @tool 装饰器自动提取参数                 |

### 三大分层记忆

| 域           | 存储                    | 工具                  |
| ----------- | --------------------- | ------------------- |
| **profile** | `profile.md`          | `save_user_profile` |
| **note**    | `MEMORY.md`           | `save_note`         |
| **session** | `AgentState.messages` | 不用工具，LLM 直接读        |

### 工具执行流程

```
LLM 生成 tool_call
    ↓
tool_policy.evaluate(context)  ← 四维判断（资源/作用域/风险/模式）
    ↓
decision == ALLOW → 真正执行
decision == ASK  → 挂起等用户确认
decision == DENY → 返回 "paused by policy"
    ↓
tool.invoke(**args)
    ↓
classify_tool_output() → 包装结果
    ↓
completion_hook 检查 AI 回复
```

### 危险工具三层防线

1. **Tool Policy**（执行前）：敏感内容/临时记忆写长期 → DENY
2. **ASK 确认**（执行中）：写文件/联网 → 等用户点确认
3. **Completion Hook**（执行后）：工具失败 AI 说成功 → 替换回复

---

## 说人话版：这些设计是怎么一步步来的

### 1. 为什么自己写 ReAct Loop，不用 LangGraph

一开始用过 LangGraph，写起来确实快，但出了问题贼难调。想象一下：AI 说它调用了工具，但工具没执行成功，它最后回复说"已保存"。你根本不知道是 LangGraph 的 loop 逻辑问题，还是工具本身问题，还是 LLM 幻觉。调试日志全是黑盒。

**LangGraph 的 loop 逻辑是什么**？核心是个状态机：

```python
# LangGraph 风格伪代码
while True:
    state = graph.get_state(current_checkpoint)  # 1. 取当前状态
    next_node = graph._get_next_node(state)       # 2. 决定下一个 node
    result = node.execute(state)                  # 3. 执行这个 node
    graph.update_state(result)                   # 4. 把结果写回状态
    if next_node == END:                         # 5. 检查是不是 end 节点
        break
```

**问题在哪**？你没法直接干预。假设 AI 返回了 tool_calls，但 LangGraph 的 `ToolNode` 发现工具报错了，它可能直接走 condition 边继续跑。加日志？LangGraph 的日志是给框架自己用的，你只能看序列化后的 checkpoint，可读性差。

**条件边是怎么回事**？LangGraph 的每个 node 执行完后，不是直接往下跑，而是先过一道"条件判断"决定下一步往哪走：

```python
# LangGraph 风格的条件边
def should_continue(state):
    # 判断基于什么？基于 LLM 返回的 content 里有没有 "saved"
    return "saved" in state["messages"][-1].content.lower()

if should_continue(state):
    goto_node_a()   # 继续下一步
else:
    goto_node_b()   # 跳到错误处理
```

**实际跑的 case**：

1. AI 说"已保存"，调用了 `save_user_profile`
2. `ToolNode` 执行，但文件权限有问题，返回了 error
3. 但 state 里这条 AI message 的 content 已经是"已保存"了
4. `should_continue()` 一看：`"saved" in "已保存"` → True
5. 所以走了 `goto_node_a()`，继续往下跑，根本没停
6. 你根本不知道 ToolNode 报错了，因为条件边的判断依据是 AI 说的"已保存"，不是工具实际返回的结果

**问题本质**：框架的"下一步往哪跑"依赖的是 AI 的文字内容，不是工具真实执行结果。你想让它在工具失败时停住？得改 `should_continue()` 逻辑，但那个逻辑是框架内部定的，你得翻它的源码才知道怎么改。

**后来自己写了个 while 循环**，就三行代码：

```python
while turn < max_turns:
    response = llm.bind_tools(tools).invoke(messages)
    for tc in response.tool_calls:
        result = tool_map[tc.name].invoke(tc.args)
        messages.append(tool_result)
```

结果发现**行数少了 10 倍，可控性高了 10 倍**。有什么问题直接加 print，比看 LangGraph 的 trace 日志爽多了。

---

### 2. Memory Scope 的分类、判断流程和演进方向

**核心判断不是背概念，而是三步**：

1. 先看持久性：这条信息以后还会不会用？如果只是当前任务进度、一次性结果、临时方案，就只留在 session，不写长期记忆。
2. 再看作用域：关于用户本人、长期偏好、身份、习惯，写全局 profile/user；关于当前项目的技术决策、约束、badcase、进展，写 project note；关于 Agent 以后应该怎么做，写 feedback；只是外部资料入口，写 reference。
3. 最后看安全性：密码、token、银行卡、身份证等敏感信息不应该写长期明文记忆；如果是隐私但允许保存，也应该只在索引里写主题，不自动注入具体值。

**例子**：

| 用户表达                      | 判断                           |
| ------------------------- | ---------------------------- |
| "我以后希望你回答简洁一点"            | 长期有效 + 用户偏好 → profile/user   |
| "这个项目约定用 poetry 管理依赖"     | 长期有效 + 当前项目约束 → project note |
| "临时记一下，今天先用 A 方案"         | 明确临时 → session，不写长期          |
| "以后不要用 echo 写中文文件，因为容易乱码" | 用户纠正 Agent 行为 → feedback     |
| "设计文档在这个链接"               | 外部资料入口 → reference           |
| "我的银行卡密码是 xxx，帮我记住"       | 敏感凭据 → 拒绝保存                  |

**当前 LightClaw 的判断方式**：靠 `infer_memory_scope(user_input, tool_name)` 做轻量规则分类，本质是关键词 + 工具名倒推：

```python
def infer_memory_scope(user_input, tool_name):
    text = user_input.lower()

    # 关键词打分
    transient_markers = ["临时", "当前会话", "本轮", "不要长期保存"]
    profile_markers = ["我喜欢", "我偏好", "我习惯", "我的偏好", "以后"]
    note_markers = ["badcase", "项目", "设计", "规范", "记录"]

    # session 优先最高——只要说了"临时"，直接认定当前会话
    if any marker in text for marker in transient_markers):
        return scope="session", confidence=0.82

    # 否则看工具名 + 关键词
    if tool_name == "save_user_profile":
        if profile_hits:
            return scope="profile", confidence=0.78
        return scope="profile", confidence=0.55  # 工具名本身暗示，但信号弱

    if tool_name == "save_note":
        if note_hits:
            return scope="note", confidence=0.74
        return scope="note", confidence=0.55
```

**当前方案的问题**：

- 关键词覆盖有限，隐式表达容易漏判，比如用户没说"偏好"，但其实是在改长期习惯
- 工具名倒推不可靠，因为模型可能先选错工具，再被 policy 误认为 scope 正确
- 缺少写前检索和冲突检测，同一主题可能 append 出多条互相矛盾的记忆
- 分类还比较粗，只有 profile/note/session，表达不了 feedback、reference、private 等语义

**参考 Abu-Cowork 的更成熟做法**：

Abu 不是把所有记忆塞进一个大文件，而是把每条记忆当成一张"小卡片"：正文之外还有标签，比如名称、描述、类型、是否隐私、创建/更新时间。

它主要分 4 类：

1. `user`：用户本人、长期目标、知识水平、回答偏好、工作习惯
2. `feedback`：用户对 Agent 行为的纠正或确认，最好包含"规则 + 原因 + 以后怎么应用"
3. `project`：项目事实、技术决策、进展、约束和 badcase
4. `reference`：外部资料入口，比如文档链接、issue、看板地址

还有 `private` 标记：隐私记忆不自动注入正文，只在索引里显示主题，用户明确问起时再读取。

**LightClaw 的演进方向**：

1. 从 `profile/note/session` 升级到 `user/feedback/project/reference/session`
2. 写入前先查索引或 recall，判断新信息是新主题、补充、冲突还是重复
3. 从纯关键词升级成规则 + LLM 分类器 + 检索混合；低置信度走 ask
4. memory write 变成结构化事务：classify → recall duplicates → policy gate → append/edit/delete → trace/eval

**面试答法**：

> 我判断记忆先看持久性，再看作用域。临时任务进度只留在 session；跨会话的用户偏好和身份写 profile；当前项目的技术决策和约束写 project note；用户对 Agent 行为的纠正可以作为 feedback；外部资料入口作为 reference。LightClaw 当前主要靠关键词和工具名倒推，优点是简单可控、方便写 eval，缺点是隐式表达和冲突处理弱。后续我会参考 Abu-Cowork 的 memdir：每条记忆独立成文件，有 type、description、private 等标签，写入前先查索引做去重和冲突判断，再决定 append、edit、delete 或 ask。

---

### 3. Completion Hooks：怎么发现 AI 在说谎

**背景**：AI 调用了工具，但工具没执行成功，它最后回复说"已保存"。

**怎么来的**：

实际 case 1 - 虚假成功：
AI 调用了 `save_user_profile`，但文件写入失败了（磁盘满权限问题），AI 看到 tool 返回了 error，结果回复用户说"已记住你的偏好"。工具失败了但 AI 声称成功。

实际 case 2 - 读后未写：
用户问"把之前那条笔记更新一下"，AI 调用了 `read_note` 读了旧内容，但更新时只追加不覆盖，结果回复说"已更新"。读了但没按预期修改。

实际 case 3 - 虚构记忆：
用户说"你之前说过怎么处理 X"，AI 直接开始复述一个根本不存在的"之前说过"的内容。原因是 AI 真的以为记住了，但实际上 memory context 是空的。

**判断逻辑**：在 `AgentHarness.run()` 里 AI 生成 final answer 后、回复用户前，每个 hook 是独立函数，输入"用户输入 + AI 回复 + state"，输出"是否替换回复"：

```python
def _apply_completion_hook(user_input, answer, state):
    # hook 1：工具失败了但声称成功
    failed_tools = [msg for msg in state.messages if msg.role == "tool" and _message_failed(msg)]
    if failed_tools and _commits_success(answer):
        return "这次操作没有成功完成，工具返回了失败结果"

    # hook 2：记忆写入意图但无成功结果
    if _memory_write_intent(user_input) and not successful_write and _commits_success(answer):
        return "我没有保存或更新这条记忆，本轮没有看到成功的写入结果"

    # hook 3：读了 note 但没更新成功
    # hook 4：无记忆来源却声称记得
    # hook 5：敏感凭据请求

    return answer  # 没毛病，不替换
```

**判断用到的标记函数**：

```python
def _message_succeeded(msg):
    return any(marker in msg.content.lower() for marker in ("saved", "updated", "note saved"))

def _message_failed(msg):
    return any(marker in msg.content.lower() for marker in ("error", "unchanged", "denied"))

def _commits_success(text):
    return any(marker in text for marker in ("已保存", "已记住", "已更新", "saved", "updated"))
```

**实际效果**：AI 说"已记住你的偏好"，但 `save_user_profile` 返回 error → 识别到 `_commits_success`=True + `_message_failed`=True → 回复被替换成"这次操作没有成功完成"。

**为什么只替换，不 retry**？

因为 retry 涉及到"重新生成"，后果难预测。让 AI 再跑一遍，它可能还是失败，也可能陷入无限 retry。而且很多失败的原因是 AI 解决不了的——磁盘满权限、网络超时，你让 AI retry 一万次也没用。

**目前策略**：检测到问题 → 替换回复告诉用户失败 → 用户自己决定下一步。如果要加 retry，合理方式是加一个"有限 retry"：工具失败后 AI 问用户"操作失败了，要重试吗"。

---

### 4. Tool Gate 门控：怎么来的

最早没这东西，AI 随便调工具。有一次跑 benchmark，AI 不停地调用 `list_office_files`，一次列出几百个文件，把 token 窗口塞满了。还有一次 AI 删文件没打招呼，直接覆盖了用户的重要文档。

**所以加了 ToolPolicy，三层决策**：

```python
class ToolGateDecision(Enum):
    ALLOW   # 直接执行
    ASK     # 弹窗让用户确认
    DENY    # 直接拒绝
```

**每个工具的权限**：

```python
permissions = {
    "save_note": ToolPermission("memory.note", "write", requires_consent=True),
    "save_user_profile": ToolPermission("memory.profile", "write", risk="high", requires_consent=True),
    "write_office_file": ToolPermission("office.file", "create", requires_consent=True),
    "web_search": ToolPermission("external.web", "search", requires_consent=True),
    "read_office_file": ToolPermission("office.file", "read"),  # 只读，直接放行
    "list_office_files": ToolPermission("office.file", "list"),
}
```

**判断流程**（`policy.evaluate(context)`）：

1. **敏感内容拦截**：用户输入或写入内容含银行卡密码、密码、token 等 → 直接 DENY
2. **临时记忆拦截**：用户说了"临时""本轮"，但 AI 想调 save_note/save_profile → 直接 DENY
3. **模式开关**：
   - `mode=off`：全部 ALLOW，不拦截
   - `mode=monitor`：记录决策但不阻止
   - `mode=enforce`：`requires_consent=True` 的工具变成 ASK，需要用户确认

**实际效果**：写文件（`write_office_file`）默认 ASK，用户点确认才执行；读文件直接 ALLOW。

**为什么要三层权限**？

- **ALLOW**：只读工具、低风险工具，直接跑不用问
- **ASK**：写文件、删数据、联网搜索，可能影响用户数据的操作，先问一句
- **DENY**：敏感操作（存密码、临时记忆写入长期），直接拒绝

**门控加在哪**？在 `AgentHarness._execute_tool_structured()` 里，**工具执行前**先过一遍 policy：

```python
def _execute_tool_structured(self, tool_name, args, ...):
    # 1. 先过 policy
    gate = self.tool_policy.evaluate(
        ToolGateContext(tool_name=tool_name, args=args, user_input=user_input)
    )
    if gate.decision != ToolGateDecision.ALLOW:
        return classify_tool_output(tool_name, "paused by policy"), gate

    # 2. policy 通过了，才真正执行工具
    result = tool_map[tool_name].invoke(**clean_args)
    return classify_tool_output(tool_name, str(result)), gate
```

**放在 LLM 和工具之间**，就像一个网关，所有工具调用都得先过我这关。

**四维度交叉判断**：这句话"按资源类型、作用域、风险等级和运行模式给出 allow/ask/deny 决策"是什么意思？

```
资源类型（resource）：工具操作的资源是什么？
  - memory.note / memory.profile → 记忆存储
  - office.file → 本地文件
  - external.web → 联网

作用域（scope）：local（本地的）还是 network（联网的）
  - 联网的工具风险更高，因为依赖外部服务

风险等级（risk）：工具本身的风险
  - low：只读，不修改数据
  - medium：会创建或修改数据
  - high：会删除或覆盖重要数据

运行模式（mode）：当前 policy 处于哪种状态
  - off：全部 ALLOW，不拦截（方便调试）
  - monitor：记日志但不阻止
  - enforce：真的拦截，requires_consent=True 的变成 ASK
```

**四维交叉判断的逻辑**：

```python
# 1. 敏感内容拦截（任何模式下都 DENY）
if contains_sensitive(args, user_input):
    return DENY, "敏感凭据禁止写入"

# 2. 临时记忆拦截（任何模式下都 DENY）
if is_temp_memory_request(user_input) and is_memory_tool(tool_name):
    return DENY, "临时请求禁止写入长期记忆"

# 3. 正常运行判断
if mode == "off":
    return ALLOW

if mode == "monitor":
    log_decision()  # 记日志但不阻止
    return ALLOW

if mode == "enforce":
    if permission.requires_consent:
        return ASK  # 需要用户点确认
    return ALLOW
```

**为什么四个都要有**？光有"风险等级"不够——off 模式下高风险工具也想让它直接跑（方便调试）。光有"运行模式"也不够——off 模式下敏感内容还是得 DENY。所以四维是交叉配合的：

| 组合                                    | 结果    | 说明                |
| ------------------------------------- | ----- | ----------------- |
| mode=off + 非敏感                        | ALLOW | 调试模式，不管风险         |
| mode=monitor + 非敏感                    | ALLOW | 记录日志，但放行          |
| mode=enforce + requires_consent=False | ALLOW | 强制模式，但不需要 consent |
| mode=enforce + requires_consent=True  | ASK   | 强制模式，需要用户确认       |
| 任何模式 + 敏感内容                           | DENY  | 兜底，不讲情面           |
| 任何模式 + 临时记忆写长期                        | DENY  | 兜底，不讲情面           |

---

### 5. Context Guard：怎么发现 context 快爆了、怎么压缩的

跑长对话时，历史消息、工具返回、长期记忆和 skill manual 都会挤占上下文。典型现象是模型开始"失忆"、重复回答，或者 provider 直接报 context too long。

**解决**：加了 `context_guard.protect_state()` 做 token 粗估、工具结果压缩和消息 trim：

```python
DEFAULT_MAX_INPUT_TOKENS = 24_000
DEFAULT_TOOL_RESULT_CHAR_LIMIT = 4_000
CONTEXT_TRIM_TRIGGER = 40   # 超这个就 trim
CONTEXT_TRIM_KEEP = 10     # 保留最近 10 轮对话
```

**token 监控/计算怎么做**：

当前不是用模型 tokenizer 精确计算，而是用字符数粗估：

```python
def estimate_tokens(text):
    return max(1, len(str(text)) // 4)

def estimate_message_tokens(messages):
    return sum(estimate_tokens(message["content"]) for message in messages)
```

`protect_state()` 会在压缩前后分别算：

- `estimated_tokens_before`
- `estimated_tokens_after`
- `compacted_tool_results`
- `trimmed`
- `summary`

这些会作为 `context_guard` event 写入 JSONL trace 和 session event，前端可以看到本轮是否发生了压缩。

**为什么用粗估**：

优点是简单、快、provider 无关，不需要为不同模型接不同 tokenizer；缺点是不精确，中文、代码、JSON、tool schema 的真实 token 都可能偏差。当前适合作为保护阈值，后续可以接 tiktoken 或 provider usage 做校准。

**压缩两层**：

**第一层：工具返回太长直接截断**（`compact_tool_result`）：

```python
def compact_tool_result(content, limit=4000):
    if len(content) <= limit:
        return content, False
    head = content[: limit//2]      # 前一半
    tail = content[-limit//2 :]     # 后一半
    omitted = len(content) - len(head) - len(tail)
    return f"{head}\n\n[context guard: omitted {omitted} chars]\n\n{tail}", True
```

- 保留前后各 2000 字符，中间插 `[context guard: omitted N chars]`
- 比如 `list_office_files` 返回 500 个文件，只留前后各一半

**为什么用"前后各 2000 字符"这种截断方式**？

因为工具返回的内容经常是"列表"或"结构化文本"，比如 `list_office_files` 返回 500 个文件路径。如果只保留前 2000 字符，你只能看到最前面几个文件，不知道最后有哪些。

**所以用 head + tail**：

- head：前 2000 字符 → 知道前面有哪些文件
- tail：后 2000 字符 → 知道最后有哪些文件
- 中间打标记：`[omitted N chars]` → 知道中间漏掉了 N 个

这是一种"首尾保留"策略，兼顾信息量和 token 节省。

**第二层：消息 trim**（`state.trim_context()`）：

```python
def trim_context(state):
    user_msgs = [(i, m) for i, m in enumerate(state.messages) if m.role == "user"]
    keep_start_idx = user_msgs[-10][0]  # 保留最近 10 个 user message

    # 早期消息提取成 summary
    old_msgs = state.messages[:keep_start_idx]
    summary_parts = []
    for msg in old_msgs:
        if msg.role == "user":
            summary_parts.append(f"User: {msg.content[:100]}...")
        elif msg.role == "assistant":
            summary_parts.append(f"Assistant: {msg.content[:150]}...")

    state.messages = state.messages[keep_start_idx:]
    state.summary = f"[Earlier conversation ({old_turn_count} turns): {'; '.join(summary_parts)}]"
```

- 超过 40 条消息，保留最近 10 轮 user+assistant
- 早期对话压缩成一段 summary：`"[Earlier conversation (N turns): User问了X... Assistant答了Y...]"`
- 工具消息全丢，因为已经体现在 summary 里了

**长期记忆和 skill 的上下文策略**：

- 当前 LightClaw 会把 `profile.md` 和 `MEMORY.md` 注入 system prompt，小规模简单有效；记忆变多后应该改成"索引 + 按需 recall"，类似 Abu-Cowork。
- skill manual 不能启动时全塞进 prompt，而是只暴露 name/description，需要时 `mode=help` 读取完整手册，再 `mode=run` 执行。

**面试答法**：

> token 监控现在是轻量字符估算，`len(text)//4` 得到 estimated tokens。每轮进 LLM 前 `protect_state()` 会先统计压缩前 token，再把超长 tool result 做 head+tail 截断，默认最多 4000 字符；如果估算 token 超过 24000 或消息数超过阈值，就触发 `state.trim_context()`，保留最近 10 个 user turn，把更早的 user/assistant 内容压成 summary 注入 system prompt。这个方案优点是简单、provider 无关，缺点是不精确，summary 也不是语义级压缩。后续可以接模型 tokenizer 或 provider usage 校准，并把长期记忆从全量注入改成索引 + 相关召回。

**口语版回答**：

> 这块我现在做得比较轻量，不是上来就接一个复杂 tokenizer，而是先做工程上的保护。因为 Agent 跑久了以后，最容易撑爆上下文的其实是三类东西：历史对话、工具返回、长期记忆和 skill 手册。所以我在每轮调用模型前都会过一层 `context_guard`。
> 
> token 数目前是粗估，简单说就是按字符数除以 4 算一个 approximate token。它不精确，但好处是快，而且不依赖具体模型供应商。这个估算主要不是为了计费，而是为了提前发现上下文快超了。
> 
> 具体处理上，第一步是压工具结果。如果一个工具返回特别长，比如列文件、读大文件、grep 结果，我不会把全文都塞回模型，而是保留开头和结尾，中间标一句省略了多少字符。这样模型还能看到结果的大概结构，也不会被一个工具结果撑爆。
> 
> 第二步是处理历史对话。如果估算 token 超过预算，或者消息数超过阈值，就保留最近的对话，把更早的 user/assistant 内容压成 summary，再把 summary 注入后续上下文。这个版本还比较朴素，summary 不是另调一个模型做深度总结，而是轻量裁剪和拼接。
> 
> 现在这个方案的优点是简单、稳定、provider 无关；缺点是 token 估算不够准，summary 也可能丢关键信息。后续我会优化成两块：一是接模型 tokenizer 或 provider 返回的 usage 做校准；二是长期记忆不要全量注入，改成像 Abu 那样只注入索引，真正相关的内容再按需 recall。

---

### 6. Heartbeat：怎么实现定时任务的

**核心就一个 producer-consumer 模式**：

```python
# pacemaker_loop = producer，每 10 秒扫一次 TASKS_FILE
async def pacemaker_loop(task_queue):
    while True:
        await asyncio.sleep(10)
        for task in check_due_tasks_once():
            await task_queue.put(format_trigger_message(task))

# Agent 消费
task_queue = asyncio.Queue()
asyncio.create_task(pacemaker_loop(task_queue))
while True:
    msg = await task_queue.get()  # 收到 "[myClaw heartbeat] A scheduled task is due..."
```

**任务存储**（`TASKS_FILE`）：

```json
[
  {"description": "写周报", "target_time": "2026-06-05 15:00:00", "repeat": "weekly"}
]
```

**一次性任务**：到期触发，直接删掉。

**周期任务**：触发后计算下次时间，重新写回文件：

- `hourly`：+1 小时
- `daily`：+1 天
- `weekly`：+7 天
- `monthly`：+1 个月，但要处理 day 边界

**月度 bug**：1 月 31 号设 monthly，+1 month 变成 2 月 31 号（不存在），程序直接崩。

**修复**：取目标月份的最后一天，`day = min(target_dt.day, last_day)`。1/31 +1month → 2/28（2026 非闰年）。

**定时任务用的 asyncio 是什么**？

Python 的异步编程库，用来处理"并发"任务——不是真正的多线程，而是单线程里切换着跑多个任务。

```python
# 同步写法：等网络返回时 CPU 闲着
result = requests.get(url)
process(result)

# 异步写法：发起请求后让出 CPU，等的时候干别的
async def fetch():
    result = await something.network_call()  # 等的时候让出 CPU
    process(result)

async def main():
    task1 = asyncio.create_task(fetch())   # 发起请求1，不等
    task2 = asyncio.create_task(fetch())   # 发起请求2，不等
    await asyncio.gather(task1, task2)     # 一起等，都好了再往下跑
```

**心跳怎么用的**：

```python
# pacemaker_loop 是一个 async 函数
async def pacemaker_loop(task_queue):
    while True:
        await asyncio.sleep(10)  # 睡 10 秒，让出 CPU，不阻塞其他代码
        for task in check_due_tasks_once():
            await task_queue.put(task)  # 塞进队列，不阻塞

# 启动方式
asyncio.create_task(pacemaker_loop(task_queue))  # 在后台跑，不阻塞主线程
```

**为什么用 async**？因为 `pacemaker_loop` 要一直跑着，每 10 秒检查一次。如果用同步写法，你得开个线程。用 async，可以单线程里跑多个协程，更轻量。

**架构**：

```
pacemaker_loop (producer)
    ↓ 往 queue 塞消息（每 10 秒检查一次）
asyncio.Queue
    ↓
Agent（consumer）
    ↓ await task_queue.get() 等待消息
收到消息 → 当作用户输入处理 → 触发提醒

---

## 项目整体架构
```

用户输入
  ↓
确定性流程（代码控制，不靠 LLM）：

1. auto_memory_write → 自动写入记忆

2. context_guard.protect_state() → 超限就压缩

3. tool_policy.evaluate() → 门控判断

4. _execute_tool_structured() → 执行工具
   ↓
   LLM 决策：

5. 生成 tool_call（调哪个工具、传什么参数）

6. 生成 final answer（说什么回复用户）

7. 决定要不要继续调用工具
   ↓
   completion_hook → 检查最终回复
   
   ```
   
   ```

**确定性的**：门控判断、context 压缩、参数校验、completion hook 替换
**LLM 决策的**：调什么工具、说什么回复、是否继续循环

---

### 7. 整体流程：哪些是确定性 workflow，哪些是 LLM 决策

**LLM/Provider 层**（`retry.py`）：

```python
def call_with_retry(fn, attempts=3, base_delay=1.0):
    for index in range(attempts):
        try:
            return fn()
        except BaseException as exc:
            if index >= attempts-1 or not is_transient_error(exc):
                raise
            time.sleep(base_delay * (2**index))  # 指数退避
```

瞬时错误（429 rate limit、timeout、503）才会 retry，磁盘满了、权限问题不会 retry。

**Tool 执行层**：工具调用失败 → 返回 error text → completion hook 检测到失败标记 → 替换回复告诉用户。

**没有**：工具失败后自动 retry 工具本身的机制，很多失败是 AI 解决不了的。

---

### 8. 失败兜底和重试机制

**Checkpoint**（`checkpoint.py`）：

```python
def write_checkpoint(session_id, **fields):
    path = CHECKPOINT_DIR / f"{session_id}.json"
    payload = {"session_id": session_id, "ts": datetime.now().isoformat(), **fields}
    path.write_text(json.dumps(payload, ...))

def read_checkpoint(session_id):
    path = checkpoint_path(session_id)
    if not path.exists(): return None
    return json.loads(path.read_text())
```

**当前实际保存的状态**：

- `session_id`：哪一个会话
- `ts`：checkpoint 写入时间
- `status`：当前跑到哪一步，比如 `llm_calling`、`llm_streaming`、`error`
- `conversation_turn`：第几轮用户对话
- `run_id`：对应哪条 JSONL trace
- `error/error_type`：异常时记录错误

**它有什么用**：

1. 崩溃/中断检测：如果程序退出时 checkpoint 还在，说明上一轮没有正常完成。
2. 前端恢复提示：可以告诉用户上一轮停在 LLM 调用、流式输出还是错误状态。
3. trace 对齐：通过 `run_id` 找到对应 JSONL 日志，看中断前发生了什么。
4. 后续断点续跑基础：未来可以把 messages、summary、pending tool call、approval 状态一起放进去，实现真正 resume。

**为什么做这个**：

Agent 一轮任务可能很长，中间可能在流式输出、等工具、等用户确认或执行文件操作。如果只靠内存，客户端崩溃或进程被杀后就不知道上一轮停在哪里。checkpoint 相当于给每轮执行打一个轻量"存档点"，先解决可观测和异常恢复提示，再逐步扩展成完整恢复。

**当前限制**：

现在 LightClaw 的 checkpoint 还不是 LangGraph 那种完整状态快照，主要记录执行状态和错误信息；对话正文主要还是 transcript 和 JSONL trace。真正的断点续跑还需要保存 `AgentState.messages`、`summary`、未完成的 tool call、policy approval 等。

**面试答法**：

> 我这里的 checkpointer 是一个轻量 turn-level checkpoint，不是复杂数据库状态机。实现上就是按 session_id 在 runtime/checkpoints 下写 JSON，记录当前状态、conversation_turn、run_id、时间戳和异常信息。正常完成后 clear，异常时保留。它的作用是让长任务中断后能知道上一轮停在哪里，并能通过 run_id 对齐 JSONL trace 做排查。当前它还不是完整 resume，只是断点检测和恢复提示的基础；后续可以把 AgentState、summary、pending tool call 和 approval 状态也写进去，变成真正的断点续跑。

**口语版回答**：

> checkpointer 可以理解成给 Agent 每一轮执行打一个很轻量的"存档点"。因为 Agent 一轮任务不是简单问答，可能会流式输出、调用多个工具、等待权限确认，甚至中途客户端崩溃。如果这些状态只存在内存里，进程一挂就不知道刚才跑到哪里了。
> 
> 所以我做了一个很轻的 checkpoint 文件。每个 session 对应一个 JSON，里面记录当前状态，比如现在是在调用 LLM、正在流式输出，还是已经报错；同时记录第几轮对话、对应哪条 run trace、时间戳和错误信息。开始执行时写 checkpoint，正常结束就清掉；如果异常退出，checkpoint 会留下来。
> 
> 它现在最大的作用是中断检测和问题定位。比如下次打开时发现 checkpoint 还在，就知道上一轮没正常结束；再通过里面的 `run_id` 找到 JSONL trace，就能看到中断前模型输入、工具调用、工具结果和 gate 决策。
> 
> 但我不会把它说成已经完整实现了 LangGraph 那种状态恢复。当前版本还不是完整 resume，更多是一个恢复基础。真正要断点续跑的话，还需要把 `AgentState.messages`、summary、还没执行完的 tool call、用户确认状态都一起持久化。这个也是后续可以继续补的方向。

---

### 9. 状态保存和恢复

**会进入死循环**：实际 case——AI 说"已保存"，但工具失败了，它又调用一次，又失败，继续回复"已保存"。

**解决方式**：

1. `max_turns=10` 限制，防止无限循环
2. Completion Hook：工具失败了但声称成功，直接替换回复说"操作失败了"
3. Tool Gate：敏感操作 ASK，防止反复执行高风险动作

**没做的**：AI 每次调工具都成功但内容重复，没有去重检测。

---

### 10. Agent 死循环问题和解决

**Schema 定义两种方式**：

```python
# @tool 装饰器自动从函数签名提取
@tool
def calculator(expression: str) -> str:
    return str(eval(expression, ...))
# 自动提取 parameters: {expression: {type: "string"}}

# 或用 Pydantic 模型
class SaveNoteArgs(BaseModel):
    action: Literal["append", "edit", "delete"]
    title: str
    content: str
```

**调用失败处理**：

```python
try:
    result = tool.invoke(**clean_args)
    return classify_tool_output(tool_name, str(result))
except Exception as e:
    return classify_tool_output(tool_name, f"Error: {str(e)}")
```

所有异常被 catch，返回 error string，不崩。

**参数错误兜底**（`FunctionTool._coerce_kwargs()`）：

```python
if param.annotation is int and isinstance(value, str):
    coerced[name] = int(value)  # "123" → 123
elif param.annotation is bool and isinstance(value, str):
    coerced[name] = value.lower() in {"1", "true", "yes", "on"}
```

字符串 "true"/"1"/"yes" 自动转 bool，不让 AI 因为传了字符串就报错。

**没做的**：参数缺失时的默认值填充、参数格式错误时的自动修正。

---

### 11. Tool Schema 定义、调用失败处理、参数兜底

**直接暴露**：工具 schema 通过 `bind_tools()` 直接传给 LLM，不经过服务端。

```
AgentHarness → llm.bind_tools(tool_schemas) → LLM
                   ↑
              工具 schema 直接给 LLM
```

**服务端做的**：只有 approval_callback 那一步需要前端确认（ASK 模式下），除此之外没有服务端来做工具分发。

**问题**：多 agent 共享工具时，没有统一的工具注册中心，每个 agent 实例自己管工具列表。

---

### 12. Tool 暴露方式、服务端分发

**定位方法**：

1. 换模型：同样 prompt 换 GPT-4o 跑一遍，好了 → 模型能力问题
2. 简化 prompt：砍到最简还不行 → prompt 设计问题
3. 加 few-shot 示例：给例子能解决 → prompt 引导不够
4. 看错误类型：
   - AI 总调错工具 → prompt 里工具描述不清楚
   - AI 不调用工具 → prompt 没强调可以用工具
   - AI 调了但参数格式错 → schema 定义或 prompt 示例有问题

**实际 case**：AI 说"已保存"但工具失败了，不是 prompt 问题，是工具执行失败了但 LLM 还是说"已保存"，靠 completion hook 才兜住。

---

### 13. 判断 prompt 没写好 vs 模型能力问题

**Case 1**：AI 调用工具时参数类型传错

- 现象：有些工具 required 没定义对
- 定位：看 tool schema 的 required 字段
- 解决：在 `FunctionTool.get_schema()` 从函数签名自动提取参数

**Case 2**：AI 不停在 ReAct loop 里

- 现象：反复调用 `list_office_files`，每次结果不一样但不停止
- 解决：加了 `max_turns=10` 限制，streaming 模式下检测重复 tool_calls 超过 N 次就强制终止

**Case 3**：AI 声称记得但根本没存（最典型的不听指令）

- 现象：工具返回 error，AI 还是说"已记住"
- 定位：靠 completion hook 的 `_commits_success` + `_message_failed` 双重检测
- 解决：替换回复，不让 AI 继续胡说

**评测数据**：目前没有系统性评测，只有 badcase 测试集（`evals/badcase_0001_context_memory.py`）。后续要加。

---

### 14. Agent 不听指令的 badcase

**Claude Code 的 memory 分三层**：

| 内容        | 存储位置                  | 工具                                      |
| --------- | --------------------- | --------------------------------------- |
| 项目规范、设计决策 | `MEMORY.md`           | `save_note`/`search_notes`              |
| 用户偏好、个人信息 | `profile.md`          | `save_user_profile`/`read_user_profile` |
| 当前对话上下文   | `AgentState.messages` | LLM 直接读取                                |

**为什么要分层**：防止混淆和幻觉。如果混在一起，AI 可能查了 MEMORY.md 里存的项目规则来回答"你老婆叫什么"。

**隔离方式**：三个东西存在不同文件，通过不同工具访问。AI 不会直接读文件，而是通过工具读。

**上下文过长处理三层**：

1. **Context Guard**：工具返回超长，head+tail 截断
2. **Context Trim**：消息超 40 条，保留最近 10 轮，早期变 summary
3. **Token 估算**：`len(text) // 4` 估算 token 数，不准但够用

---

### 15. Claude Code Memory 机制和分层记忆

1. **Tool Policy 硬拦截**：敏感内容（银行卡密码、token）→ DENY；临时记忆写入长期 → DENY
2. **ASK 确认**：写文件、联网搜索默认 ASK，用户点确认才执行
3. **Completion Hook 兜底**：工具失败了但 AI 声称成功 → 替换回复

**没做的**：危险操作次数限制（5 分钟内最多删 3 次文件）

---

### 16. 防止调用危险工具的三层防线

**背景问题：为什么需要懒加载**

如果每个 skill 的完整 manual 都塞进 prompt，token 爆了。有 50 个 skill，每个 manual 3000 字，那就是 15 万 token。

**所以改成：先只列出 skill 名字和一句话描述，等 AI 说"我要用这个"，再加载完整 manual。**

**两阶段调用**：

**第一阶段：help** —— AI 看一眼 skill 是干嘛的

```python
# 只返回 name + description，不加载完整 SKILL.md
skill_registry = [
    {"name": "code_review", "description": "帮你做代码审查"},
    {"name": "git_helper", "description": "帮你处理 git 操作"},
]
# AI 看到"code_review"这个名字，决定要用这个
# → 调用 skill_tool(mode="help") → 返回完整 SKILL.md
```

**第二阶段：run** —— AI 读完 manual，决定怎么用

```python
# AI 看完 help，返回的内容里有：
# "If this skill fits the task, call this same tool again with mode='run' and a concrete command."
# → AI 调用 skill_tool(mode="run", command="cd {baseDir} && python review.py --file main.py")
```

**LazySkillLoader 核心逻辑**：

```python
class LazySkillLoader:
    def _scan_skills(self):
        # 1. 只扫目录，找 SKILL.md 文件
        # 2. 从文件头 50 行提取 name + description
        # 3. 不读完整内容，只存路径/mtime
        return skill_registry  # [{name, description, md_path, mtime}, ...]

    def _create_lazy_tool(self, skill_info):
        def lazy_runner(mode, command=""):
            if mode == "help":
                # 2. 真正读取 SKILL.md 完整内容
                content = self._load_skill_content(md_path, mtime)
                return f"========== [{skill}] manual ==========\n{content[:3000]}\n" \
                       "If this skill fits, call with mode='run' and command."

            if mode == "run":
                # 3. 执行具体命令
                actual_cmd = command.replace("{baseDir}", f"skills/{folder}")
                return execute_office_shell.invoke({"command": actual_cmd})

        return FunctionTool(lazy_runner, name=skill_info["name"], description=skill_info["description"])
```

**流程图**：

```
LLM 说"我要用 code_review"
    ↓
第一阶段：mode="help"
    ↓ 读 SKILL.md 完整内容
返回完整的 code_review manual + 用法说明
    ↓
LLM 决定具体命令
    ↓
第二阶段：mode="run", command="python review.py main.py"
    ↓ 执行命令
返回结果
```

**懒在哪**？

- **扫描阶段**：只读文件名 + 前 50 行提取 metadata，不读完整内容
- **LRU 缓存**：同一个 SKILL.md 内容只读一次，60 秒内不重复读
- **真正加载**：只在 `mode="help"` 时才读完整文件

**实际效果**：AI 说"帮我看看有哪些 skill 可用"——直接列出 50 个 skill 的名字和一句话描述，不触发任何文件 IO。等 AI 说"用 xxx"，才真正读那个文件。

**用在训练场景**：训练数据生成时，可以让 agent 按需调用不同的训练脚本 skill，不用一开始就把所有脚本 manual 都塞进 prompt。

---

### 17. CyberClaw 额外 Harness 约束（LightClaw 对照）

#### 1. 文件工具沙箱：`Path.resolve()` + 父目录校验（已有）

**为什么需要**：AI 会受到提示词注入的影响，或者为了"方便"直接读取 `../../etc/passwd`、`~/.ssh/` 等系统路径。

**具体 case**：用户让 AI"帮我看看上周的日志"，AI 理解成"查看所有日志"，顺着路径往上走读到 `/var/log/` 下的系统日志。如果 AI 能读 SSH 配置，那私钥都泄露了。

```python
# files.py 里的 _safe_path()
office_root = OFFICE_DIR.resolve()
candidate = (OFFICE_DIR / normalized).resolve()
if candidate != office_root and office_root not in candidate.parents:
    raise ValueError("path escapes the myClaw office sandbox")
```

这里的思路很简单：先把允许访问的根目录算出来，比如：

```text
/Users/baiding/LightClaw/workspace/office
```

再把 AI 传进来的路径也算成真实绝对路径。比如：

```text
notes/a.txt
```

会变成：

```text
/Users/baiding/LightClaw/workspace/office/notes/a.txt
```

这个路径的父目录链里包含 `office_root`，所以放行。

如果 AI 传：

```text
../../README.md
```

拼起来看似还在 office 下面，但 `.resolve()` 会把 `..` 全部折叠掉，最后变成：

```text
/Users/baiding/LightClaw/README.md
```

这个路径已经不在 `workspace/office` 里面，所以拦截。

它比单纯字符串 `startswith()` 更稳，因为它还会处理符号链接。比如 office 里有个软链接指到 `~/.ssh`，`.resolve()` 会追到真实目标，发现最终路径不在 office 里，也会拦掉。✅ LightClaw 已有。

#### 2. Shell local backend：`cwd` 锁定 + 正则拦截（默认已有）

**为什么需要**：AI 可以通过 `execute_office_shell` 工具绕过文件 API 的限制，使用 `cat /etc/hosts` 或 `rm -rf /` 等原生命令对操作系统造成毁灭性破坏。

**具体 case**：AI 被要求"清理一下磁盘空间"，它执行了 `rm -rf /`——如果没有拦截，整个系统被删空。或者是 `sudo su` 提权后为所欲为。

默认 backend 是：

```bash
MYCLAW_SHELL_BACKEND=local
```

也就是直接在宿主机上跑：

```python
subprocess.run(command, shell=True, cwd=str(OFFICE_DIR), timeout=60)
```

这层做了两件事：

1. `cwd=OFFICE_DIR`：命令从 `workspace/office/` 启动。
2. `_check_command_safety()`：执行前先扫命令字符串，发现明显越界就拒绝。

```python
# shell.py 里的 _check_command_safety()
_ESCAPE_PATTERNS = [
    r"\.\.",                        # ../ 路径穿越
    r"(?:^|\s|[<>|&;])/",           # Unix 绝对路径 /etc
    r"(?:^|\s|[<>|&;])~",           # 用户主目录 ~
    r"(?:^|\s|[<>|&;])\\",          # Windows 路径 \
    r"(?i)(?:^|\s|[<>|&;])[a-z]:",  # Windows 盘符 C:
]
_BLOCKED_COMMANDS = [
    r"^\s*sudo\s",                  # sudo 提权
    r"^\s*chmod\s+777",              # 权限全开
]
```

这能挡住显式危险命令，比如：

```bash
cat /etc/passwd
ls ~
ls ../
sudo whoami
```

但这不是完整 OS 级沙箱。因为 shell 进程本质仍在宿主机上跑，`cwd` 只是默认工作目录，不等于"只能看到这个目录"。正则也只能拦命令字符串里直接出现的危险符号，挡不住程序运行后动态做的事情：

```bash
# 读宿主进程继承的环境变量
python -c 'import os; print(os.environ)'

# 动态询问 home 目录，而不是命令字符串里写 "~"
python -c 'import pathlib; print(pathlib.Path.home())'

# 通过 Python 联网，而不是直接 curl/wget
python -c 'import urllib.request; print(urllib.request.urlopen("https://example.com").read()[:20])'

# 启动大量子进程或吃内存
python -c 'import subprocess; [subprocess.Popen(["sleep","60"]) for _ in range(1000)]'
```

所以 local backend 的定位是：开发期、可信用户、基础防误操作。它比裸 shell 安全，但不能当多租户或不可信代码的硬隔离。

#### 3. Shell docker backend：本地容器硬隔离（新增）

**为什么需要**：local backend 不能真正限制进程运行后的文件系统、网络、资源和子进程行为。Docker backend 的目标是把普通 shell 命令放进容器里跑，即使 AI 运行了脚本，脚本看到的也是容器环境，而不是完整宿主机。

开启方式：

```bash
MYCLAW_SHELL_BACKEND=docker
MYCLAW_DOCKER_IMAGE=python:3.12-slim
```

执行链路从：

```text
agent -> execute_office_shell -> subprocess.run(command, cwd=office)
```

变成：

```text
agent -> execute_office_shell -> docker run ... /bin/sh -lc command
```

当前 Docker 参数：

```bash
docker run --rm \
  --pull missing \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --memory 512m \
  --cpus 1 \
  --pids-limit 128 \
  --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  -e HOME=/workspace \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v {OFFICE_DIR}:/workspace:rw \
  -w /workspace \
  python:3.12-slim \
  /bin/sh -lc "{command}"
```

几个关键点：

- `-v {OFFICE_DIR}:/workspace:rw`：容器只拿到 office 目录，AI 产物仍能落回本地 workspace。
- `--network none`：默认禁网，Python/Node 脚本也出不了网。
- `--read-only`：容器根文件系统只读，只有 `/workspace` 和 `/tmp` 可写。
- `--memory 512m` / `--cpus 1` / `--pids-limit 128`：限制内存、CPU、进程数，防止资源打爆。
- `--cap-drop ALL` + `no-new-privileges`：尽量去掉容器里的 Linux capabilities 和提权路径。
- `--pull missing`：镜像本地没有时才拉；也可以设 `MYCLAW_DOCKER_PULL=never` 禁止运行时拉镜像。

Docker backend 的效果是：即使命令里运行 `python -c 'open("/etc/passwd").read()'`，读到的也是容器内 `/etc/passwd`，不是宿主机文件。即使脚本尝试联网，也会被容器网络配置拦住。

可配置项：

```bash
MYCLAW_DOCKER_IMAGE=python:3.12-slim
MYCLAW_DOCKER_PULL=missing
MYCLAW_DOCKER_NETWORK=none
MYCLAW_DOCKER_MEMORY=512m
MYCLAW_DOCKER_CPUS=1
MYCLAW_DOCKER_PIDS=128
```

注意：Docker 仍然是共享宿主 kernel 的容器隔离，不是 Firecracker/Kata 这种 VM 级隔离。但对当前 LightClaw 的第一阶段来说，它已经把文件系统、网络和资源限制从"字符串规则"升级到了"运行时边界"。

#### 4. Shell 超时与非交互检测（已有）

**为什么需要**：LLM 调用 Shell 时可能会启动阻塞式交互命令（如 `npm install` 等待确认，或者进入 Python REPL），后台进程会永久挂起，锁死运行队列。

**具体 case**：AI 执行 `pip install pandas`，但这是个交互式安装，需要输入 `y` 确认。进程挂起等待输入，永远等下去，导致整个 Agent 卡死。

```python
# shell.py
SHELL_TIMEOUT = 60  # 强制超时熔断
# 检测交互式命令
if result.returncode != 0 and ("prompt" in stderr.lower() or "y/n" in stdout.lower()):
    output += "\nHint: Command may require confirmation. Use -y or --yes flags."
```

60 秒超时 + 非交互检测，保证 AI 永远不会被挂起的交互命令卡死。✅ LightClaw 已有。

#### 5. 当前沙箱分层怎么回答面试官

可以这样概括：

```text
文件工具：Path.resolve() + office_root parents 校验，防路径穿越和软链接逃逸。
Shell local：cwd 锁到 office + 正则拦明显危险路径/提权命令 + 60s timeout。
Shell docker：把命令放进本地容器，默认禁网、只挂 office、限 CPU/内存/进程。
Tool policy：在工具执行前做权限 gate，高风险写操作可以 ASK。
```

如果被问："为什么有了正则还要 Docker？"

回答：

> 正则只能检查命令字符串，挡不住程序运行后动态构造路径、读环境变量、联网、fork 子进程或吃内存。Docker 是运行时边界，能从文件系统、网络和资源层面限制进程。local backend 更像防误操作，docker backend 才更接近真正 sandbox。

如果被问："Docker 会不会很麻烦？"

回答：

> 起容器本身不复杂，只要基础镜像已经在本地，`docker run --rm` 是短生命周期执行。真正麻烦的是依赖下载，所以第一阶段用 `python:3.12-slim` 这种基础镜像跑普通 shell；后面可以预构建 `lightclaw-sandbox` 镜像，把 Python/Node/rg/git 等常用工具提前装好，避免每次任务临时安装。

#### 6. 计算器安全 eval（已有）

**为什么需要**：原生 `eval(expression)` 会执行任意 Python 表达式。如果大模型接收到恶意输入计算 `__import__('os').system('rm -rf /')`，整个系统就被攻破了。

**具体 case**：用户让 AI"帮我计算一下这个表达式的值"，恶意对手通过提示词注入让它计算 `open('/etc/passwd').read()`——没有沙盒的话能直接读系统文件。

```python
# builtins.py
result = eval(expression, {"__builtins__": {}}, {})
```

清空 `__builtins__` 可以阻止一切系统内置函数的调用，**仅保留基础数学运算**。✅ LightClaw 已有。

---

### 18. Skill 懒加载：渐进式披露 vs 原生懒加载

**原生 Skill 渐进式披露（CyberClaw）**：

传统方式：AI 看到所有 skill 的 description，然后直接选一个调用。但 description 再长也是摘要，可能选错。

CyberClaw 的两阶段：

```
第一阶段：AI 看到 skill 名字 + 摘要描述，决定"我要用这个"
第二阶段：AI 读完整的 SKILL.md 说明书，再决定"具体怎么用"
```

如果读完后发现不对，可以换别的 skill，不会有决策撤回的风险。

**LightClaw 的懒加载**：

```
扫描阶段：只读文件夹名 + SKILL.md 前 50 行提取 name/description
首次调用（mode=help）：才真正读完整 SKILL.md，缓存 60 秒
执行阶段（mode=run）：执行具体命令
```

**区别**：

| 机制    | CyberClaw 两阶段           | LightClaw 懒加载    |
| ----- | ----------------------- | ---------------- |
| 第一阶段  | 选 skill（description 决策） | 扫 metadata（不读文件） |
| 第二阶段  | 读 SKILL.md（确认决策）        | 读完整内容（mode=help） |
| 决策撤回  | 可以换 skill               | 不支持（读完就执行）       |
| 准确率提升 | 40%                     | 无数据              |

**为什么有效**：两阶段让 AI 有"后悔"的机会。看 description 觉得合适，但读完 manual 发现用法不对，可以换。传统方式读完 manual 发现选错了，已经晚了。

**LightClaw 的改进方向**：可以在 `mode=help` 返回后加一轮决策确认——"这个 skill 适合你的需求吗？适合的话我执行，不适合我继续找"。

---

### 19. LRU 缓存机制（轻量扫描/首次加载/缓存失效）

**先说清楚三件事**：

- 懒加载：需要时才读完整 `SKILL.md`，不是启动时全读。
- LRU 缓存：读过的 `SKILL.md` 先放内存缓存，下次同一个文件直接复用；超过上限时淘汰最近最少使用的。
- 两阶段加载：先 `help` 读说明、确认是否适合，再 `run` 执行具体命令。

**三步机制**：

```python
from functools import lru_cache

@lru_cache(maxsize=50)
def _load_skill_content(md_path: str, mtime: float) -> str:
    return Path(md_path).read_text(encoding="utf-8")

def _scan_skills(self, force_rescan=False):
    # 1. 轻量扫描：只读前 50 行提取 metadata
    if not force_rescan and cached:
        return self._skill_registry

    for folder in SKILLS_DIR.iterdir():
        md_path = folder / "SKILL.md"
        metadata = _extract_metadata(md_path)  # 只读前 50 行
        skills.append({**metadata, "md_path": str(md_path), "mtime": ...})

    return skills
```

**轻量扫描**：启动时只扫描目录，不读文件内容。从 SKILL.md 前 50 行提 name + description 元数据，立即返回。

**首次调用时加载**：只有在 `mode="help"` 时才通过 `@lru_cache` 读取完整文件内容。60 秒内重复调用同一个 skill，不重复读文件。

**缓存自动失效**：读取时用 `mtime`（文件修改时间）做缓存 key。文件一旦修改，`mtime` 变化，缓存自动失效，无需重启 Agent。

**两阶段加载流程**：

```text
启动/扫描阶段：
  只读取每个 SKILL.md 前 50 行，提取 name 和 description
  → prompt 里只暴露 skill 名字和一句话描述

help 阶段：
  模型认为某个 skill 可能有用，调用 mode="help"
  → 这时才读取完整 SKILL.md，并返回 manual

run 阶段：
  模型读完 manual，生成具体 command，调用 mode="run"
  → 执行命令并返回结果
```

**LRU 为什么要带 mtime**：

`@lru_cache(maxsize=50)` 的 key 是函数参数。LightClaw 把 `md_path` 和 `mtime` 都作为参数：

```python
@lru_cache(maxsize=50)
def _load_skill_content(md_path: str, mtime: float) -> str:
    return Path(md_path).read_text(encoding="utf-8", errors="replace")
```

这样同一个文件没修改时，重复 `help` 直接命中缓存；如果 `SKILL.md` 被修改，文件修改时间变了，缓存 key 也变了，就会重新读，不会一直用旧手册。

**面试答法**：

> Skill 懒加载是为了避免把所有 `SKILL.md` 塞进 prompt。启动时我只扫 skill 目录，读前 50 行提取 name 和 description；模型需要某个 skill 时，先调用 `mode=help`，这时才读取完整手册；读完后再调用 `mode=run` 执行具体命令。完整手册读取用了 LRU 缓存，最多缓存 50 个，缓存 key 带文件修改时间，所以重复读取快，文件改了也会自动失效。

---

### 20. 未做的 Harness 约束（待实现）

#### 1. 时间模糊确认死锁协议（Time Ambiguity Protocol）

**为什么需要**：AI 在处理自然语言时间时，经常会擅自假定默认值（如"默认早上7点"），但在闹钟/日历场景中，这种假定可能导致严重失误。

**具体 case**：用户说"7点提醒我开会"，AI 直接设了早上 7:00，结果用户要的是晚上 7:00。AI 没有提问就自作主张，用户错过了一个重要会议。

**CyberClaw 的做法**：

```python
# schedule_task 工具中
if is_ambiguous_time(user_input):
    return "Error: 时间存在歧义（12小时制），必须向用户确认是早上还是晚上。
绝对禁止自行猜测。在得到明确答复前，此工具锁定。"
```

**LightClaw 需要做**：在 `schedule_task` 工具里检测 12 小时制歧义（只有 "X点" 没有 "上午/下午/早上/晚上"），直接拒绝并要求用户确认。

#### 2. 模糊批量删除安全熔断（Fuzzy Destruction Guard）

**为什么需要**：大模型在面临删除任务时，其提取的意图容易"扩大化"，可能误将其他相似任务一并抹除。

**具体 case**：用户说"把那个 5 天的任务删了"，系统匹配到了 3 个任务：1）5天前的周报、2）每5天执行一次的任务、3）标题里带"5天"的任务。AI 看了看，决定全删——结果把那个"每5天执行一次"的定时任务也删了，用户还不知道。

**CyberClaw 的做法**：

```python
if fuzzy_delete_command and matched_count > 1 and no_specific_id:
    return "Error: 模糊删除匹配到多个任务。必须向用户展示列表并要求确认具体 ID。"
```

**LightClaw 需要做**：在 `cancel_task`/`modify_task` 中，如果用户描述模糊（无具体 task_id）但匹配到多个，强制展示列表要求确认。

#### 3. Completion Hook 强化（从关键词到 Trace 审计）

**为什么需要**：关键词匹配太粗糙，AI 可以通过改写词汇绕过检测（比如用"存储完毕"代替"已保存"）。

**具体 case**：AI 调用 `save_user_profile`，工具返回 error，但 AI 回复说"已为您妥善保管"。关键词 `"已保存"` 检测不到，但实际上是谎话。或者是 AI 用了"搞定"、"记住了"、"存好了"等变体，关键词匹配完全失效。

**CyberClaw 的做法**：

```python
# 检查 Trace 日志，确认工具真正执行了
trace_log = get_tool_trace_log(tool_call_id)
if trace_log.status == "failed" and "已保存" in answer:
    return "操作实际未完成，工具执行失败：{trace_log.error}"
```

**LightClaw 的改进方向**：

```python
# 1. 给每个工具调用分配 tool_call_id
# 2. 在 trace 日志里记录执行结果（success/fail/error_message）
# 3. completion_hook 读取 trace 而非关键词
if tool_result.metadata.get("tool_ok") is False and commits_success(answer):
    return f"操作实际未完成：{tool_result.metadata.get('error')}"
```

---

### 21. 隐式记忆问题：工具名倒推的漏洞和修复方向

**为什么需要关注**：AI 靠工具名倒推判断 scope，但 AI 可能调错工具——该用 `save_user_profile` 用了 `save_note`，导致用户偏好混进项目笔记里，下次问"我老婆叫什么"时 AI 读到了项目文档的片段。

**具体 case**：

| 用户输入           | AI 实际调用                                    | 问题                                                          |
| -------------- | ------------------------------------------ | ----------------------------------------------------------- |
| "小红是我老婆"       | `save_note(type="user", content="小红是我老婆")` | 用户偏好写进了 note，下次问"我老婆"，AI 从 note 读到了，但 note 是项目知识，不该回答用户个人问题 |
| "这个项目用 poetry" | `save_user_profile(content="项目用 poetry")`  | 项目知识写进 profile，profile 越来越臃肿，混入了非个人偏好的内容                    |

**Abu-Cowork 的做法**（更完善）：

```typescript
// 4 种 memory type
type MemoryType = 'user' | 'feedback' | 'project' | 'reference'

// 每个文件有 frontmatter
interface MemoryFrontmatter {
  name: string
  description: string
  type: MemoryType
  source: 'agent_explicit' | 'auto_flush' | 'user_manual'
  created: number
  updated: number
  private: boolean  // 私有记忆不自动注入
}
```

**Abu-Cowork 的流程**：

1. **写之前先判断**：`infer_memory_scope()` 在工具执行**前**判断，不是在执行后倒推
2. **写的时候带 type**：tool call 包含 `type='user'` 或 `type='project'` metadata
3. **两步写**：写 .md 文件 + 更新 MEMORY.md 索引
4. **读的时候过滤**：scan 时按 type 过滤，private 不自动注入

**LightClaw 改进方向**：

```python
# 工具执行前加校验
decision = infer_memory_scope(user_input, tool_name)
if decision.scope == "profile" and tool_name != "save_user_profile":
    log_warn(f"Expected save_user_profile but got {tool_name}")
    # 可以让 AI 重新选择，或直接 DENY
```

---

### 22. 为什么简单替换不够：分层处理和状态恢复

**为什么需要分层**：失败有很多种，有的可以 retry，有的只能告诉用户，有的需要人工介入。眉毛胡子一把抓，全部"替换成失败提示"，用户体验很差。

**具体 case**：

| 失败类型                | 当前行为      | 用户体验                       |
| ------------------- | --------- | -------------------------- |
| 网络超时 429            | 替换成"操作失败" | 用户莫名其妙，明明再试一次可能就成了         |
| 磁盘满了                | 替换成"操作失败" | 用户想知道是空间不足，需要清理，而不是一个无用的错误 |
| 工具返回 error 但 AI 说成功 | 替换成"操作失败" | 这个是对的，但用户不知道是工具崩了还是 AI 撒谎  |
| 文件权限不够              | 替换成"操作失败" | 用户需要知道要改权限或用管理员身份运行        |

**Claude Code 的做法**：不做强制替换，让 LLM 自己感知失败原因并重新生成。如果 LLM 反复失败，才让用户介入。

**OpenClaw 的做法**（推测）：

1. **瞬时失败**（timeout/429）：retry 机制
2. **工具参数错误**：返回错误让 LLM 重新生成参数
3. **LLM 幻觉说成功**：completion hook 检测并替换
4. **不可恢复失败**：直接告诉用户，让用户决定

**更完善的做法**：

```python
# 分层处理
if is_transient_error(e):  # timeout/429
    return retry_with_backoff()
elif is_llm_hallucination(failed_result, answer):  # 工具成功但 LLM 说谎
    return replace_with_fact(failed_result)
elif is_user_error(e):  # 权限/参数问题
    return explain_to_user(e)
```

**目前没做**：分层处理、状态恢复、实际结果反馈给 LLM 重新生成。

---

### 23. Agent 完整跑一圈：结合 Harness 设计详解

**场景**：用户说"帮我把 office 文件夹里大于 100MB 的文件都移到一个叫'待整理'的文件夹里"

这个任务拆成4步：

1. 列出 office 文件夹里的所有文件
2. 找出大于 100MB 的文件
3. 在 office 里建一个"待整理"文件夹
4. 把大文件移进去

每一步都会触发不同的 Harness 约束，中间还会穿插 Context Guard 和 Completion Hook 检查。

---

**Step 1：列出 office 里的文件**

```
用户输入："帮我把 office 文件夹里大于 100MB 的文件都移到一个叫'待整理'的文件夹里"
```

**Harness 触发点**：

1. **Tool Policy（只读工具，直接放行）**
   
   ```python
   tool_policy.evaluate(
       tool_name="list_office_files",
       args={"path": "."},
       user_input=用户输入
   )
   ```
   
   - `list_office_files` 的 `requires_consent=False`，直接 ALLOW

2. **Physical Sandbox（路径安全）**
   
   ```python
   # AI 调工具时传入 path="."
   _safe_path(".") → OFFICE_DIR/. → 在沙盒内 ✓
   ```

3. **Context Guard（对话轮数检查）**
   
   - 对话刚开始，消息只有 1-2 条，Context Guard 不触发
   - 如果用户已经聊了 50 轮，这里会先 trim 再继续

**执行结果**：返回 office 目录下的文件列表

---

**Step 2：过滤大于 100MB 的文件**

```
AI：execute_office_shell(command="find . -type f -size +100M")
```

**Harness 触发点**：

1. **Shell 危险命令正则拦截**
   
   ```python
   _check_command_safety(command)
   # 命令：find . -type f -size +100M
   ```
   
   - 检查 `..`（路径穿越）→ 没有
   - 检查 `~`（用户主目录）→ 没有
   - 检查 `/unix absolute` → 没有
   - 检查 `_BLOCKED_COMMANDS`（sudo/chmod 777）→ 没有
   - **通过！**
   
   **如果 AI 写错了**：
   
   ```
   AI: find ~/Desktop -type f -size +100M
   # _check_command_safety 检测到 ~
   # 拦截！返回 "Error: detected dangerous directory escape pattern"
   ```

2. **SHELL_TIMEOUT = 60**
   
   - 如果 office 目录有几万个文件，find 可能跑很久
   - 超过 60 秒 → 超时熔断，返回超时错误

**执行结果**：返回大于 100MB 的文件列表，如

```
./downloads/video.mp4 (150MB)
./backups/db.sqlite (120MB)
```

---

**Step 3：在 office 里建"待整理"文件夹**

```
AI: write_office_file(path="待整理", content="")
```

**Harness 触发点**：

1. **Tool Policy（ASK 确认）**
   
   ```python
   tool_policy.evaluate(
       tool_name="write_office_file",
       args={"path": "待整理", "content": ""},
       user_input="移到叫'待整理'的文件夹里"
   )
   ```
   
   - `write_office_file` 是创建文件的操作，`requires_consent=True`
   - `mode=enforce` → 返回 ASK + "paused by policy"
   - **暂停**，前端弹出确认框

2. **Physical Sandbox（路径校验）**
   
   - `"待整理"` 是相对路径，拼到 `OFFICE_DIR` 下
   - `_safe_path("待整理")` → OFFICE_DIR/待整理/ → 在沙盒内 ✓

**等待用户确认期间**：

```
用户看到弹窗："是否允许创建文件 待整理？"
用户点"允许"
↓ 继续执行
↓ 工具真正创建了这个目录
```

---

**Step 4：把大文件移进去**

```
AI: execute_office_shell(
    command="mv downloads/video.mp4 downloads/db.sqlite 待整理/"
)
```

**Harness 触发点**：

1. **Shell 危险命令正则拦截**
   
   ```python
   _check_command_safety(command)
   ```
   
   - 路径里没有 `..`、`~`、\、`C:` 等危险字符 ✓
   - 命令是 `mv`（移动文件），不在 `_BLOCKED_COMMANDS` 里 ✓

2. **Tool Policy**
   
   - `execute_office_shell` 的 `requires_consent=False`，直接 ALLOW

3. **SHELL_TIMEOUT = 60**
   
   - 如果文件很大（几个 GB），mv 可能跑很久
   - 超过 60 秒 → 超时熔断

---

**Step 5：AI 生成了回复，Completion Hook 检查**

```
AI 生成的回复：
"已完成！找到了 2 个大于 100MB 的文件（video.mp4、db.sqlite），已移动到'待整理'文件夹。"
```

**Completion Hook 检查**

```python
def _apply_completion_hook(user_input, answer, state):
    # Hook 1：工具失败了但声称成功
    failed_tools = [msg for msg in state.messages
                    if msg.role == "tool" and _message_failed(msg)]
    if failed_tools and _commits_success(answer):
        return "这次操作没有成功完成，工具返回了失败结果"

    # Hook 2：记忆写入但无成功结果
    # （本轮没有 save_user_profile/save_note，跳过）

    return answer  # 没毛病，不替换
```

**本轮情况**：

- `list_office_files` → 成功
- `execute_office_shell(find)` → 成功
- `write_office_file` → 成功（用户点了确认）
- `execute_office_shell(mv)` → 成功
- `_commits_success(answer)` = True（"已完成"）
- 没有失败工具 → Hook 不拦截

**但如果 mv 失败了**（比如磁盘满了）：

```
execute_office_shell 返回："Error: [Errno 28] No space left on device"
AI 生成的回复："已完成！找到了 2 个大于 100MB 的文件...已移动到'待整理'文件夹"
    ↓
completion_hook 检查：
    - _failed_tools = [execute_office_shell tool result]
    - _commits_success("已完成") = True
    ↓
两个条件都满足 → 拦截！
    ↓
回复被替换成：
"这次操作没有成功完成，工具返回了失败结果（磁盘空间不足）。
请稍后重试。"
```

---

**如果中途出问题，Harness 怎么拦截**

| 场景                          | Harness 拦截点                       | 结果        |
| --------------------------- | --------------------------------- | --------- |
| AI 用 `~/Desktop` 而不是 office | `_ESCAPE_PATTERNS` 拦截 `~`         | 返回"危险命令"  |
| AI 用 `../../etc/passwd`     | `_safe_path()` 拦截路径穿越             | 返回"越权拦截"  |
| 写文件时用户拒绝确认                  | `tool_policy.evaluate() → ASK`    | 工具暂停，不执行  |
| mv 命令跑了 90 秒                | `SHELL_TIMEOUT = 60`              | 超时熔断      |
| mv 失败但 AI 说"搞定"             | `completion_hook` 拦截              | 替换成"操作失败" |
| AI 企图删整个 office             | `_BLOCKED_COMMANDS` 拦截 `rm -rf *` | 返回"危险命令"  |
| 定时任务触发但 AI 在忙               | task 进 queue 等 Agent 空闲           | 不丢任务      |
