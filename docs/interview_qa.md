# LightClaw 项目面试 QA

---

## 项目概览

### 项目定位

个人 AI 助手 harness（agent 运行框架），自己写 ReAct loop，不用 LangGraph，追求轻量可控。

**为什么做这个**：想做个人 AI 助手——能记住我的偏好、能跑定时任务、能调工具。最开始用 LangGraph，但黑盒太多调试不了，后来自己写 ReAct。

**相比 OpenClaw 的优势**：OpenClaw 是通用框架，定制化要翻它的代码，很多我们需要的东西它没有：分层记忆（profile/note）、completion hooks 防说谎、tool gate 门控。LightClaw 定位是轻量、可控、专注个人助手场景。

面试里不要把它讲成“我做了一个聊天机器人”，而要讲成 **透明可控的 Agent Harness / Agent Runtime**。它解决的核心问题是：当 AI 开始自己调用工具、读写文件、修改记忆、执行命令、处理后台任务时，系统怎么知道它做了什么，怎么限制它不能乱做，出问题后怎么复盘。

简历上可以压缩成这样：

> 设计并实现一个透明可控的 Agent Harness，支持原生 ReAct 循环、长短期记忆、上下文压缩、工具注册与分发、ToolGate 权限控制、Office/Shell 沙盒、定时任务、Skill 懒加载、流式 trace 展示和 agent 级评测闭环。

### 典型任务场景

这些任务不是 demo 清单，而是后续评测和 badcase 固化的来源。每补一个 harness 能力，都应该能在这些任务上看到行为变化。

| 场景       | 典型输入                                                   | 主要验证点                               |
| -------- | ------------------------------------------------------ | ----------------------------------- |
| 时间查询     | `现在几点了？`                                               | 是否能选择时间工具，结果是否进入 trace              |
| 数学计算     | `帮我算一下 25 乘以 48`                                       | 是否调用计算器工具，而不是纯猜答案                   |
| 定时任务     | `每天早上 8 点提醒我喝水`                                        | 是否创建循环任务，任务是否持久化                    |
| 修改任务     | `把 8 点的喝水提醒改成 9 点`                                     | 是否定位已有任务并更新，而不是新建重复任务               |
| 文件读写     | `读取 readme.txt` / `创建 test.py`                         | 是否遵守 office sandbox，写入是否避免误覆盖       |
| Shell 执行 | `运行 python test.py`                                    | 是否在 office sandbox 内执行，是否有超时和危险命令拦截 |
| 用户画像     | `记住我喜欢喝冰美式`                                            | 是否写入长期 profile，后续 session 是否可注入     |
| 项目记忆     | `把这个项目约定记下来：eval trace 统一用 JSON suite`                 | 是否写 note 而不是写 user profile          |
| Skill 安全 | `给新实习生开通 VPN 权限`                                       | 是否先看 skill manual，避免望文生义误用工具        |
| 监控分析     | 实时看 `llm_input`、`tool_call`、`tool_result`、`ai_message` | 是否能复盘模型输入、工具决策、工具结果和最终回复            |

### 面试重难点地图

| 优先级 | 主题                  | 面试重点                                   | 常见追问                       |
| --- | ------------------- | -------------------------------------- | -------------------------- |
| P0  | 原生 ReAct loop       | 为什么不用 LangGraph，自己写 loop 得到了什么可控性      | tool result 怎么回灌、怎么停止死循环   |
| P0  | ToolGate + 沙盒       | prompt 软约束如何变成执行前硬边界                   | 为什么 off 也要保留硬安全 deny       |
| P0  | Memory Scope        | profile/note/session 怎么分，临时信息为什么不能长期保存 | 隐式偏好怎么处理                   |
| P0  | Trace + Eval        | 怎么证明改动有效，不只是感觉变好                       | badcase 怎么从 trace 固化成 eval |
| P1  | Context Guard       | 长任务怎么防止上下文爆炸                           | 为什么先压 tool result，再裁历史     |
| P1  | Skill 两阶段           | 为什么 help→run 能减少危险工具误用                 | 代价是什么，怎么 benchmark         |
| P1  | Heartbeat / Runtime | 后台任务怎么进 agent loop                     | 并发和 session 污染怎么避免         |

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

更完整地讲，LightClaw 不是把所有记忆塞进一个文件，而是按“会不会跨 session、属于用户还是项目、能不能自动注入”来分层：

| 类型           | 适合存什么                     | 生命周期      | 主要风险             |
| ------------ | ------------------------- | --------- | ---------------- |
| Session      | 当前任务进度、临时偏好、本轮上下文         | 当前对话      | 不能误写长期           |
| User Profile | 稳定偏好、身份、工作习惯              | 跨 session | 不能存密码、token、隐私明文 |
| Project Note | 项目约定、技术决策、badcase、eval 结论 | 项目级长期     | 不能和用户画像混淆        |
| Trace        | 模型输入、工具调用、权限判断、工具结果       | 调试/评测     | 不能当作长期记忆直接注入     |

**Session JSON 和 Trace JSONL 的区别**：

| 文件                            | 内容                                                                          | 用途                    |
| ----------------------------- | --------------------------------------------------------------------------- | --------------------- |
| `sessions/{session_id}.json`  | 用户和 assistant 最终对话                                                          | 继续对话，保持 transcript 干净 |
| `runs/interactive-*.jsonl`    | `llm_input`、`tool_call`、`tool_gate_decision`、`tool_result`、`agent_hook` 等事件 | 调试、回放、转 eval          |
| `workspace/memory/profile.md` | 用户长期画像                                                                      | 跨 session 注入          |
| `workspace/memory/MEMORY.md`  | 项目 note                                                                     | 项目知识召回                |

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

**如果面试官问 Agent 还有哪些常见架构**，可以这样答：

| 架构               | 优点                       | 缺点                               | 适合场景            |
| ---------------- | ------------------------ | -------------------------------- | --------------- |
| 单轮工具调用           | 实现简单、延迟低、成本低             | 一次决策错了很难修正，工具链条短                 | 简单查询、简单计算、单工具任务 |
| ReAct loop       | 能边执行边观察，错误可在下一轮修正，适合开放任务 | 可能循环过长，需要 max_turns、权限和 trace 约束 | 文件操作、检索、调试、复杂问答 |
| Plan-and-execute | 计划清晰，适合拆解长任务             | 计划一开始错了会把错误传播到后续步骤               | 流程型任务、批处理、项目执行  |
| Multi-agent      | 角色分工清楚，可加入审核者            | 通信成本高，状态一致性难，容易互相甩锅              | 大型研究、代码审查、复杂协作  |
| Workflow/状态机     | 可控性最强，路径稳定，方便审计          | 灵活性低，新增场景要改流程                    | 审批、客服工单、固定业务流程  |

**为什么最终选 ReAct**：

> 因为当前重点是构建通用 agent harness，而不是只跑固定流程。ReAct 足够灵活，又能把每次工具调用变成可观察的 step。为了控制 ReAct 的不稳定性，工程层补 max_turns、ToolGate、trace、参数预校验、context guard 和 completion hook。ReAct 负责灵活性，harness 负责边界和可控性。

**项目里的关键 hook 插点**：

| Hook                  | 触发位置                     | 做什么                                                | 为什么需要               |
| --------------------- | ------------------------ | -------------------------------------------------- | ------------------- |
| `before_llm_input`    | 每个 ReAct step 调模型前       | 构建 system prompt、注入 profile/summary、记录 `llm_input` | 让模型输入可复盘            |
| `before_tool_execute` | 模型产生 tool call 后、工具执行前   | 参数预校验、ToolGate、memory scope、source routing、用户确认    | 把 prompt 软约束变成执行硬边界 |
| `after_tool_execute`  | 工具返回后                    | 记录 `tool_result`，把 observation 写回 state            | 让模型下一轮看到真实结果        |
| `on_gate_decision`    | gate 产生 allow/deny/ask 后 | 写 `tool_gate_decision`，ask 时通知前端弹窗                 | 高风险工具可被用户介入         |
| `on_context_trim`     | 输入过大或消息过多时               | 压缩 tool result、裁历史、写 summary                       | 防止上下文爆炸             |
| `completion_hook`     | 最终答案发给用户前                | 校验工具结果和回复是否一致                                      | 防止工具失败后 AI 说成功      |
| `on_stream_event`     | 流式运行时                    | 输出 content/tool_call/tool_result/final 事件          | 前端实时展示 ReAct step   |

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

**已经硬化的记忆写入保护**：

| 风险              | 保护方式                                   |
| --------------- | -------------------------------------- |
| 重复 note 反复创建    | `save_note` 对相同内容做去重，避免 `MEMORY.md` 膨胀 |
| 空 profile 覆盖旧画像 | 空内容 update/remove 会被拒绝                 |
| 敏感凭据长期保存        | ToolGate 在任何模式下直接 DENY                 |
| 临时偏好写长期         | memory scope 判为 session 时直接 DENY       |
| profile 冲突      | 写入 conflict notice，提醒后续人工或更强策略处理       |

所以 memory 系统不是“模型想记就写”。稳定路径应该是：先判断 scope，再过 ToolGate，再由具体工具做写入保护，最后通过 trace/eval 观察有没有误写。

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

**先说当前项目里有哪些 hook**：

面试里我一般不会一上来讲得很抽象。我会说：LightClaw 里的 hook 其实就是几个关键插点，专门卡在 Agent 最容易出问题的位置。模型可以自由思考、自由决定要不要调工具，但一到真正执行工具、写记忆、回复用户这些关键动作，就不能只靠 prompt 约束，要有代码层面的检查。

当前主要有这几类：

1. **工具执行前的 ToolGate hook**
   
   这个 hook 插在模型生成 `tool_call` 之后、工具真正执行之前。简单说就是：AI 说"我要调用这个工具"，但系统先问一句"这个工具能不能现在执行？"
   
   它会看工具类型、参数、用户原话和当前策略。比如：
   
   - 用户说"这次会话临时记一下"，AI 却想写长期记忆，ToolGate 会拦住。
   - 用户让记住银行卡密码、token、API key，ToolGate 会直接拒绝。
   - AI 想联网搜索，但问题其实是在问当前项目里的内容，ToolGate 可以要求先走本地来源。
   - 高风险工具在 `default` 或 `auto` 模式下不是直接执行，而是返回 `ASK`，等用户确认。
   
   所以它的作用不是"记录一下"，而是真正的执行边界。prompt 只能劝模型别乱来，ToolGate 是代码层面不让它乱来。

2. **工具执行后的 observation hook**
   
   工具执行完以后，结果会被写回 state，变成下一轮 LLM 能看到的 observation。这里虽然现在没有单独起一个 `after_tool_execute` 函数名，但它实际就是一个 hook 点。
   
   它的价值是把"工具到底发生了什么"留在上下文里：成功、失败、被拒绝、参数缺失，都会变成下一轮模型能看到的证据。没有这个环节，模型很容易工具失败了还继续幻想"我已经完成了"。

3. **最终回复前的 completion hook**
   
   这个是最典型的防说谎 hook。它插在 AI 已经生成 final answer 之后、真正发给用户之前。
   
   它会检查：AI 最后说的话，和前面真实工具结果是否对得上。比如工具失败了，但 AI 说"已保存"；没有加载到记忆，但 AI 说"我记得"；读了 note 但没成功 edit，却说"已更新"。这些都会被替换成更诚实的回复。
   
   我理解它不是为了让 AI 更聪明，而是让系统更老实。LLM 负责生成，hook 负责兜底核验。

4. **LLM 输入前的 context guard hook**
   
   每一轮把消息送进模型前，会先检查上下文是不是太长，尤其是 tool result 有没有特别大。太长的工具结果会被压缩，历史太多会被裁剪。
   
   这个 hook 解决的是另一个问题：不是安全，而是可控。Agent 跑多轮之后，如果把所有历史和大段工具输出都塞给模型，成本会涨，效果也会变差。context guard 就像一个进模型前的整理员，保证输入别爆掉。

5. **trace / stream event hook**
   
   还有一类是观测用的 hook。比如 `llm_input`、`tool_call`、`tool_gate_decision`、`tool_result`、`ai_message`、`agent_hook` 这些事件都会被写到 trace，流式模式下也会发给前端。
   
   它不一定拦截执行，但很重要，因为它让每一步都能复盘。面试时我会强调：Agent 不是只看最终答案，必须能看到模型每一步输入、调用了什么工具、工具返回什么、哪个 hook 改写了回复。否则 badcase 很难定位。

**一句话总结**：

> 我把 hook 分成三类：执行前拦截、执行后留证据、最终回复前兜底。ToolGate 管"能不能做"，observation 管"做完发生了什么"，completion hook 管"最后有没有乱说"，context guard 管"上下文别失控"，trace hook 管"每一步都能复盘"。

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

**所以加了 ToolPolicy，三种结果、四种模式**：

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

1. **deny rules 先跑**：敏感凭据、临时信息写长期记忆、危险 shell、越权路径 → 直接 DENY
2. **mode check 再跑**：
   - `mode=off`：普通权限直接 ALLOW，但硬安全 DENY 仍生效
   - `mode=default`：需要 consent 或未命中规则的灰区操作返回 ASK
   - `mode=plan`：只允许读，不允许写入、修改或联网
   - `mode=auto`：只读和低风险工具自动放行，中高风险工具返回 ASK
3. **allow rules 后跑**：只读工具、明确低风险工具 → ALLOW
4. **兜底 ASK**：前面都没命中，就让用户确认

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
  - default：灰区和需要 consent 的操作先 ASK
  - plan：只读模式，写入、修改、联网都 DENY
  - auto：只读和低风险自动放行，中高风险 ASK
```

**四维交叉判断的逻辑**：

```python
# 1. deny rules 先跑
if matches_deny_rule(tool_name, args, user_input):
    return DENY

# 2. mode check
if mode == "off":
    return ALLOW

if mode == "plan":
    if is_write_tool(tool_name) or is_network_tool(tool_name):
        return DENY

if mode == "auto":
    if is_read_only_tool(tool_name):
        return ALLOW
    if permission.requires_consent:
        return ASK

if mode == "default":
    if permission.requires_consent:
        return ASK

# 3. allow rules
if matches_allow_rule(tool_name, args):
    return ALLOW

# 4. 兜底
return ASK
```

**为什么四个都要有**？光有"风险等级"不够，因为同一个中风险工具在 plan 模式要拒绝，在 default 模式要询问，在 auto 模式也可能因为只读/低风险被放行。光有"运行模式"也不够，因为不管哪个模式，敏感凭据和临时信息写长期记忆都必须 DENY。所以四维是交叉配合的：

| 组合                                   | 结果    | 说明          |
| ------------------------------------ | ----- | ----------- |
| mode=off + 非敏感                       | ALLOW | 调试模式，不管风险   |
| mode=plan + 只读工具                     | ALLOW | 计划模式允许读取    |
| mode=plan + 写入或联网                    | DENY  | 计划模式不做副作用   |
| mode=auto + 只读工具                     | ALLOW | 自动模式直接放行低风险 |
| mode=default + requires_consent=True | ASK   | 默认模式需要用户确认  |
| 任何模式 + 敏感内容                          | DENY  | 兜底，不讲情面     |
| 任何模式 + 临时记忆写长期                       | DENY  | 兜底，不讲情面     |

**hook、event、UI 三者不要混淆**：

| 层           | 作用                                        | 是不是安全边界                 |
| ----------- | ----------------------------------------- | ----------------------- |
| Policy hook | `ToolPolicy.evaluate()` 决定 allow/ask/deny | 是，没 allow 就不会执行工具       |
| Trace event | 写入 `tool_gate_decision`、`tool_result`     | 不是，只负责审计和复盘             |
| UI approval | 前端弹窗让用户允许/拒绝                              | 是用户决策入口，但最终仍由后端 gate 执行 |

也就是说，事件只是“传话”和“观测”。真正的边界是 `_execute_tool_structured()` 里这句逻辑：`gate.decision != ALLOW` 就直接返回 denied/paused observation，不调用 `tool.invoke()`。

**ASK 怎么等待前端确认**：

1. Python 侧生成一个 `request_id`，把 `tool_gate_decision` 事件发给前端。
2. 前端展示工具名、参数、权限、风险、memory scope、source routing 和 reason。
3. 用户点击允许/拒绝后，Tauri 写入 `runtime/approvals/<request_id>.json`。
4. Python 等到允许就继续执行工具；拒绝或超时就返回“工具未执行”的 observation。

这个本地文件桥接方案不复杂，但优点是可调试、trace 清楚，而且没有把安全边界放到前端。前端只是让用户表达决策，后端才决定工具是否真的执行。

**Source Routing 在 ToolGate 里的角色**：

它不是直接回答问题，而是在模型准备调用联网工具时判断“这次是否应该先查本地”。比如用户问“myClaw 的 gate policy 是怎么实现的”，模型如果想 `web_search`，source routing 会给出 `local_first`，并把 `source_route`、`source_route_confidence`、`local_source_hits` 写入 trace。

口语版可以这么说：

> 我不是简单禁 web，也不是模型想搜就搜。Source routing 做的是信息缺口判断：这个问题是不是当前项目、当前会话、trace、workspace 或记忆里已经有答案？如果是，就先 local_first；如果是新闻、价格、官网文档这类时效信息，再允许 network。这样比默认禁网灵活，也比默认联网可控。

---

### 5. Context Guard：怎么发现 context 快爆了、怎么压缩的

这块面试里我会先说人话：Agent 和普通聊天最大的区别是，它不是只收用户几句话。它还会把历史对话、工具返回、长期记忆、skill 手册一起塞给模型。任务一长，上下文就像背包一样越塞越满，最后会出现三种问题：模型开始忘前面的约束、重复干同一件事，或者 provider 直接报 `context too long`。

所以 LightClaw 这里做了一个 `context_guard.protect_state()`，作用不是让模型更聪明，而是在每次进模型前先整理一下输入：大工具结果先压一压，历史消息太多再裁一裁，整个过程都写进 trace，方便后面复盘。

**当前核心参数**：

```python
DEFAULT_MAX_INPUT_TOKENS = 24_000
DEFAULT_TOOL_RESULT_CHAR_LIMIT = 4_000
CONTEXT_TRIM_TRIGGER = 40   # 总消息数超过 40 条才考虑 trim
CONTEXT_TRIM_KEEP = 10     # 保留最近 10 个 user turn
```

**token 监控/计算怎么做**：

当前不是用模型 tokenizer 精确计算，而是用字符数粗估。简单说，就是先不追求特别准，先有一个便宜、稳定、provider 无关的预警：

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

这些会作为 `context_guard` event 写入 JSONL trace 和 session event。这样前端能看到这一轮压缩前多大、压缩后多大、有没有截断工具结果、有没有裁历史。

**为什么用粗估**：

优点是简单、快、provider 无关，不需要一开始就为不同模型接 tokenizer。缺点也很明确：中文、代码、JSON、tool schema 的真实 token 都可能和 `len(text)//4` 有偏差。所以它更像安全带，不是计费器。后续可以接 tiktoken 或 provider usage 做校准。

**压缩两层**：

**第一层：先压工具结果**

工具结果是最容易突然撑爆上下文的东西。比如 `grep` 扫出几千行、读了一个大日志、列出几百个文件，如果原样回灌给模型，后面几轮基本就被这些输出淹没了。

所以 `compact_tool_result()` 会对超过 4000 字符的 tool message 做 head + tail 压缩：

```python
def compact_tool_result(content, limit=4000):
    if len(content) <= limit:
        return content, False
    head = content[: limit//2]      # 前一半
    tail = content[-limit//2 :]     # 后一半
    omitted = len(content) - len(head) - len(tail)
    return f"{head}\n\n[context guard: omitted {omitted} chars]\n\n{tail}", True
```

这里不用简单的"只保留前面"，而是保留开头和结尾：

- head：看到结果开头，知道这是什么东西
- tail：看到结果结尾，很多命令的结论或报错在最后
- omitted marker：明确告诉模型中间省略了多少，不让它误以为看到了全文

这个策略很朴素，但对日志、文件列表、命令输出都比较实用。

**第二层：再裁历史消息**

如果压完工具结果以后，估算 token 还是超过预算，就调用 `state.trim_context()`。这里要注意一个细节：当前代码触发条件是总消息数超过 40 条，不是 40 个用户轮次。因为一次工具调用通常会产生 user、assistant tool_call、tool result 好几条消息，所以工具密集任务会更早触发 trim。

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

裁剪逻辑可以理解成：

- 最近 10 个 user turn 之后的消息完整保留，保证刚刚发生的事不丢。
- 更早的 user/assistant 会被截短拼成 `state.summary`。
- 更早的 tool message 不进 summary，主要是为了避免旧工具输出继续撑爆上下文。
- 裁剪后 `state.tool_results` 会清空，避免旧 observation 混进新的推理。

这里有一个工程取舍：summary 不是另起一个 summarizer 模型做深度总结，而是同步、轻量地截断拼接。优点是快、稳定、不引入额外模型调用；缺点是它不是语义级摘要，早期关键信息如果没有被 user/assistant 说清楚，可能会丢。尤其是工具输出，如果 assistant 没在回答里复述，老 tool result 被裁掉以后就不能指望模型还记得。

**长期记忆和 skill 的上下文策略**：

- 当前 LightClaw 会把 `profile.md` 和 `MEMORY.md` 注入 system prompt，小规模简单有效；记忆变多后应该改成"索引 + 按需 recall"，类似 Abu-Cowork。
- skill manual 不能启动时全塞进 prompt，而是只暴露 name/description，需要时 `mode=help` 读取完整手册，再 `mode=run` 执行。

**怎么验证 context guard 没有只是“看起来能跑”**：

`manual_context_compression_cases.md` 里设计的是长任务手工 case，不是普通单元测试。它覆盖的重点可以这样讲：

| Case                       | 验证点                                  | 为什么重要                              |
| -------------------------- | ------------------------------------ | ---------------------------------- |
| Basic multi-turn           | 多轮后触发 trim，最近事实还能保留                  | 防止历史裁剪把当前任务剪坏                      |
| Tool-heavy ReAct           | 工具密集任务会早于 40 个 user turn 触发          | 因为触发条件是总消息数，不是用户轮数                 |
| Oversized tool result      | 大工具输出只保留 head + tail                 | 防止 grep/list/read 大结果撑爆上下文         |
| Summary excludes tool logs | 旧 tool result 不应完整进 summary          | 防止 summary 继续携带巨量日志                |
| Temporary constraint       | 临时约束被压缩后也不能写长期记忆                     | 防止 context trim 造成 memory scope 污染 |
| Recent turn fidelity       | 最近几轮必须完整保留                           | 保证当前任务连续性                          |
| Resume boundary            | session transcript、summary、长期记忆来源要分清 | 防止模型把 summary 误说成长期记忆              |

这类 case 的价值是专门打“长任务边界”：不是问模型一个简单问题，而是让它经历读文件、压缩、继续任务、再回答来源问题，观察它是否因为上下文裁剪开始幻觉。

**面试答法**：

> 我这里把上下文压缩做成了两道闸。第一道是工具结果压缩，因为 Agent 最容易爆上下文的不是用户说太多，而是工具一下返回几千行日志或者文件列表。所以我会先对超过 4000 字符的 tool result 做 head + tail 截断，保留开头和结尾，中间明确标记省略了多少字符。第二道是历史消息裁剪，如果估算输入超过预算，就保留最近 10 个 user turn，把更早的 user/assistant 截短拼成 summary，再注入后续上下文。
> 
> token 预算现在是轻量估算，按 `len(text)//4` 算 approximate token。它不精确，但足够做保护阈值，而且不依赖具体 provider。这个方案的优点是简单稳定，缺点是 summary 不是语义级压缩，旧 tool result 也不会进 summary。所以我会要求真正重要的工具结论要进入 assistant answer、note 或后续摘要，而不是只留在 tool observation 里。

**口语版回答**：

> 这块可以理解成：模型每次开口前，我先帮它整理书包。历史聊天、工具输出、长期记忆、skill 手册全都往里塞，跑长任务时书包一定会爆。所以我在每轮调用模型前都会过一层 `context_guard`。
> 
> 第一步先看有没有特别大的工具输出。比如读日志、跑 grep、列文件，工具可能一下吐几千行。我不会把全文都塞回模型，而是留开头、留结尾，中间写清楚省略了多少。这样模型大概知道发生了什么，又不会被一坨日志淹没。
> 
> 第二步才是裁历史。如果上下文还是太大，就保留最近 10 个用户轮次，因为最近发生的事最容易影响当前决策；更早的对话压成一段 summary。这个 summary 现在不是另一个模型总结的，就是一个轻量的截断拼接，所以它快、稳定，但也会丢细节。
> 
> 这里我特别注意一点：tool result 不是长期知识。旧的工具输出被裁掉以后，如果 assistant 当时没有把关键结论说出来，也没有写进 note，那后面就不应该假装还知道。所以这个机制不只是压缩，也是在逼 agent 把真正重要的结论沉淀到回答或记忆里。
> 
> 后续优化方向也很清楚：token 估算可以接真实 tokenizer 或 provider usage；summary 可以换成结构化 summarizer；长期记忆不要全量塞 prompt，而是先注入索引，相关内容再按需 recall。

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

```text
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

**确定性的**：门控判断、context 压缩、参数校验、completion hook 替换
**LLM 决策的**：调什么工具、说什么回复、是否继续循环

---

### 7. Gateway、路由与并发边界

这块的面试重点不是“有一个入口函数”，而是一次用户输入进入系统后，怎么被整理成一个可执行 turn，怎么隔离 session、trace、权限配置和后台任务。

**当前 Gateway 在哪里**：

| 入口              | 文件                             | 作用                                    |
| --------------- | ------------------------------ | ------------------------------------- |
| CLI             | `main.py`                      | 本地交互入口，适合开发调试                         |
| One-turn runner | `interactive_turn.py`          | 客户端、eval 和流式运行共同使用的 turn 执行器          |
| Tauri command   | `client/src-tauri/src/main.rs` | 桌面端调用 Python 进程、读取 run/session/policy |
| React client    | `client/src/main.tsx`          | 展示会话、trace、工具、权限确认和文件预览               |

**一次请求进来后 Gateway 要准备的东西**：

1. session id：决定历史 transcript 从哪里读、结果写到哪里。
2. history：把已有 user/assistant 对话恢复成 `AgentState`。
3. tools：把内置工具、文件工具、shell 工具、动态 skill 绑定给模型。
4. policy config：决定当前是 `off/default/plan/auto` 哪种权限模式。
5. trace logger：给本轮 run 分配 run id，记录每个 ReAct step。
6. approval callback：遇到 `ASK` 时通过前端弹窗等待用户确认。

**路由解析分三类**：

| 路由             | 解决什么问题                        | 典型判断                                            |
| -------------- | ----------------------------- | ----------------------------------------------- |
| Memory Scope   | 这句话该不该写长期记忆，写 profile 还是 note | “以后/我习惯”偏 profile，“项目约定”偏 note，“临时/本轮”偏 session |
| Source Routing | 该先查本地还是联网                     | 问当前项目、已有记忆时 local_first；问实时新闻、外部网页时 network     |
| Tool Policy    | 工具能不能执行                       | 写文件、联网、shell 走权限 gate，危险路径和敏感记忆直接 deny          |

**并发已经做了什么**：

- 任务文件有 `tasks_lock`，避免多个任务 CRUD 同时写 JSON。
- 心跳任务通过队列进入 agent，而不是直接抢当前 turn 的 state。
- 每个 run 有独立 JSONL trace，前端按 session/turn/react_step 分组。
- 流式模式下，后端逐行 emit 事件，前端实时更新，不等整轮结束。

**还没做完整的并发控制**：

- 没有 per-session lock，同一 session 如果同时发两轮，可能互相污染 transcript。
- checkpoint 还不是完整 `AgentState` 快照，不能从任意 ReAct step 精确恢复。
- 写操作还没有统一 idempotency key，重复提交可能产生重复副作用。
- 后台 heartbeat 和用户交互的优先级策略还比较朴素。

口语版可以这么说：

> Gateway 的价值是把一次用户输入整理成一个边界清楚的 turn。模型只负责做决策，但 session 恢复、工具注册、权限模式、trace 归属、前端确认和后台任务排队都在 harness 里确定下来。现在已经能保证 trace 和任务文件比较清楚，下一阶段要补的是 per-session lock、idempotency key 和更完整的 checkpoint resume。

---

### 8. 整体流程：哪些是确定性 workflow，哪些是 LLM 决策

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

### 9. 失败兜底和重试机制

**面试里可以先这么讲**：

> 我这里的失败处理不是只靠一句 prompt 让模型"出错了自己想办法"，而是在 Agent 外面做了几层工程兜底。简单说就是：模型调用失败，可以重试；工具调用失败，不能让程序崩，而是把失败结果写回 observation；工具失败了但模型还说成功，completion hook 会把回复改诚实；上下文快爆了，context guard 会提前压缩；流式进程崩了，前端能收到 `stream_error`，trace 里也能查到。
> 
> 所以它现在更像一个轻量可靠性框架：先保证失败可见、失败不乱报成功、失败能复盘。它还不是 Temporal 或 LangGraph 那种完整工作流恢复系统，后续要补的是幂等、session 锁、工具级 retry、模型 fallback 和真正的断点续跑。

**当前分了几层**：

1. **LLM/provider 层：只重试瞬时错误**
   
   比如 429、rate limit、timeout、500/502/503 这类，一般是网络或服务端抖动，重试一次可能就好了。所以 `retry.py` 里做了最多 3 次指数退避。
   
   但它不会对所有错误都 retry。比如参数错、权限错、磁盘满了，这种再调三次也没意义，应该直接暴露出来。

2. **工具执行层：失败变成 observation**
   
   工具执行前先过 ToolGate，敏感操作会拒绝或等用户确认。真正执行工具时，未知工具、缺必填参数、工具内部异常都会被 catch，然后转成 `Error: ...` 的工具结果写回 state。
   
   这里的关键是：工具失败不是 Python 直接崩掉，而是变成模型下一轮能看到的证据。这样模型有机会修正参数，或者至少不能假装工具成功了。

3. **工具结果层：把文本结果分类**
   
   工具返回后会被 `classify_tool_output()` 分成 `ok`、`updated`、`error`、`unchanged`、`denied` 这几类，并写进 tool message metadata。
   
   这一步是为了让后面的 hook 和 trace 不只看一大段字符串，而是能知道这个工具到底算成功、失败、没变更，还是被策略拦了。

4. **最终回复层：防止 AI 失败后说成功**
   
   completion hook 会在最终答案发给用户前做一次核验。比如用户让保存记忆，但本轮没有成功写入；或者工具已经返回 error，模型却说"已完成"。这种回答会被替换成更诚实的失败说明。
   
   这层不是为了让模型更聪明，而是为了让系统更老实。因为真实工具结果比模型最后一句话更可信。

5. **上下文层：防止输入撑爆**
   
   每次调用模型前会先跑 context guard。大的工具输出会做 head + tail 压缩，历史太长会 trim，并把压缩信息写进 trace。
   
   这也是一种兜底：不是等 provider 报 `context too long` 再崩，而是调用前先控制输入规模。

6. **运行时和前端层：失败能看见**
   
   一轮任务开始会写 checkpoint，异常时保留错误类型和 run_id。流式模式下，Tauri 后端如果遇到子进程启动失败、stdout 捕获失败、JSON 解析失败、进程异常退出，都会发 `stream_error` 给前端。
   
   所以用户不会只看到界面卡住，开发者也能顺着 checkpoint 和 JSONL trace 查到失败发生在哪一步。

**一句话总结**：

> 当前 LightClaw 的思路是：能自动恢复的瞬时错误就有限重试；不能自动恢复的工具错误就结构化暴露；模型如果无视失败乱说成功，就由 completion hook 兜住；整条链路都写 trace，保证后面能复盘。它解决的是"失败别静默、别撒谎、别把系统带崩"，更高级的幂等重放和持久任务队列还属于下一阶段。

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

### 10. 状态保存和恢复

**会进入死循环**：实际 case——AI 说"已保存"，但工具失败了，它又调用一次，又失败，继续回复"已保存"。

**解决方式**：

1. `max_turns=10` 限制，防止无限循环
2. Completion Hook：工具失败了但声称成功，直接替换回复说"操作失败了"
3. Tool Gate：敏感操作 ASK，防止反复执行高风险动作

**没做的**：AI 每次调工具都成功但内容重复，没有去重检测。

**会话恢复和模型输入构建顺序**：

恢复会话时，不是把所有历史、记忆、summary 混成一坨塞给模型，而是按层次组装：

```text
1. system prompt：ReAct 协议、工具边界、记忆规则
2. long-term memory：profile.md、MEMORY.md 的当前内容
3. state.summary：如果发生过 context trim，注入早期摘要
4. session messages：最近保留的 user/assistant/tool 消息
5. 当前用户输入
```

这个顺序的好处是来源清楚：profile/note 是长期记忆，summary 是压缩后的会话上下文，session messages 是近期原始 transcript。面试里要强调，trace JSONL 不会直接注入给模型，它是调试和评测材料；如果要从 trace 里提炼知识，应该先经过 memory scope 或 note 写入流程。

**当前恢复能力的边界**：

| 能恢复什么                   | 不能恢复什么                  |
| ----------------------- | ----------------------- |
| 用户/assistant transcript | 任意 ReAct step 的中间状态     |
| 长期 profile/note         | 未落盘的临时 tool observation |
| policy config           | 正在等待的用户确认状态             |
| run trace 复盘            | 直接从 trace 自动继续执行        |

所以现在的 checkpoint 更偏“可观测和可复盘”，还不是生产级 workflow resume。真正的断点续跑需要保存完整 `AgentState`、pending tool call、approval request、idempotency key 和 session lock。

---

### 11. Agent 死循环问题和解决

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

### 12. Tool Schema 定义、调用失败处理、参数兜底

**工具生命周期可以按 5 步讲**：

| 阶段        | 发生在哪里                                  | 做什么                                               |
| --------- | -------------------------------------- | ------------------------------------------------- |
| 定义        | `core/tools/*.py`                      | 用 `@tool` 装饰普通函数，保留函数签名和 docstring                |
| Schema 生成 | `BaseTool.get_schema()`                | 从函数名、参数类型、docstring 生成 LLM 可读 schema              |
| 注册        | `ALL_TOOLS` / `create_agent_harness()` | 组装内置工具、文件工具、shell 工具、动态 skill                     |
| 暴露        | `llm.bind_tools(tool_schemas)`         | 每轮把工具 schema 交给模型，让模型产生 structured tool call      |
| 执行        | `_execute_tool_structured()`           | 校验参数、过 ToolGate、调用 `tool.invoke()`、分类 tool result |

所以工具不是“LLM 直接运行 Python 函数”。LLM 只能输出工具名和 JSON 参数；真正查表、校验、权限判断和调用函数都在 harness 里。

**直接暴露**：工具 schema 通过 `bind_tools()` 直接传给 LLM，不经过服务端。

```
AgentHarness → llm.bind_tools(tool_schemas) → LLM
                   ↑
              工具 schema 直接给 LLM
```

**服务端做的**：只有 approval_callback 那一步需要前端确认（ASK 模式下），除此之外没有服务端来做工具分发。

**问题**：多 agent 共享工具时，没有统一的工具注册中心，每个 agent 实例自己管工具列表。

**当前工具存储边界**：

| 工具类型         | 数据落点                          | 约束                      |
| ------------ | ----------------------------- | ----------------------- |
| Profile      | `workspace/memory/profile.md` | 用户长期偏好，不存敏感凭据           |
| Notes        | `workspace/memory/MEMORY.md`  | 项目知识、badcase、设计记录       |
| Office files | `workspace/office/`           | 文件读写和 shell 都锁在 sandbox |
| Tasks        | `~/.myclaw/tasks/tasks.json`  | 任务 CRUD 有线程锁            |
| Trace        | `runs/*.jsonl`                | 只做审计和 eval，不直接当长期记忆     |

**未来如果扩展成 MCP / 多 agent 工具中心**：

> 当前是每个 harness 实例自己拿 `ALL_TOOLS`，简单直接。下一步可以把工具注册拆成 registry：本地内置工具、动态 skill、MCP server 工具都先进入统一 registry，再按 agent/session/policy 暴露子集。这样就能实现“某个 agent 看不到危险工具”“某个 session 临时禁用联网”“某类工具必须二次确认”。

---

### 13. Tool 暴露方式、服务端分发

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

### 14. 判断 prompt 没写好 vs 模型能力问题

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

### 15. Agent 不听指令的 badcase

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

### 16. Claude Code Memory 机制和分层记忆

1. **Tool Policy 硬拦截**：敏感内容（银行卡密码、token）→ DENY；临时记忆写入长期 → DENY
2. **ASK 确认**：写文件、联网搜索默认 ASK，用户点确认才执行
3. **Completion Hook 兜底**：工具失败了但 AI 声称成功 → 替换回复

**没做的**：危险操作次数限制（5 分钟内最多删 3 次文件）

---

### 17. 防止调用危险工具的三层防线

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

### 18. CyberClaw 额外 Harness 约束（LightClaw 对照）

这一节面试时可以先用“硬边界 vs 软约束”概括。硬边界是代码已经拦住的路径；软约束是 prompt/docstring 里要求模型遵守，但还需要 eval 持续压测。

如果只讲当前 shell sandbox 的主线，可以直接说：**现在强隔离版本是基于 Docker 的**。local backend 还保留着，主要是为了开发调试和兼容旧流程；真正要跑不可信 shell 命令时，应该切到 Docker backend。

| 类型  | 机制                             | 当前状态                                         |
| --- | ------------------------------ | -------------------------------------------- |
| 硬边界 | Task 文件线程锁                     | 已实现，防并发写坏 JSON                               |
| 硬边界 | Office 文件 `_safe_path()`       | 已实现，防路径穿越和软链接逃逸                              |
| 半硬化 | Shell local cwd + 正则 + timeout | 已实现，主要用于开发调试和兼容旧流程                           |
| 硬边界 | Shell docker backend           | 当前强隔离 shell sandbox，基于 Docker 容器限制文件系统/网络/资源 |
| 硬边界 | Pre-execution 参数校验             | 已实现，缺 required args 不执行工具                    |
| 硬边界 | Task 时间格式与未来时间校验               | 已实现，非法时间和过去时间拒绝                              |
| 硬边界 | Calculator restricted eval     | 已实现，清空 `__builtins__`                        |
| 硬边界 | ToolGate deny rules            | 已实现，敏感记忆、临时记忆写长期、危险 shell 直接拒绝               |
| 半硬化 | Memory Scope / Source Routing  | 已写入 gate trace，部分用于 deny/ask，仍需 eval 压测      |
| 软约束 | 模糊时间追问、批量删除确认、工具选择语义           | 主要靠 docstring/prompt，后续要继续硬化                 |

这张表的重点是：LightClaw 不是只靠 prompt。“会造成真实副作用”的边界尽量放到工具执行前或工具内部；“语义上是否该做”的边界先做 trace/eval，再逐步硬化。

#### 1. 文件工具沙箱：先把路径“摊平”，再看它还在不在 office 里

**先讲人话版**：

文件工具只允许碰 `workspace/office/`。不管模型传进来的是 `notes/a.txt`，还是 `../../README.md`，代码都会先把路径算成一个真实的绝对路径，然后检查：这个最终路径到底还在不在 office 目录里面。

如果还在，就放行；如果跑到外面了，就直接报错。

**为什么要这么做**：

模型可能不是故意攻击，它只是“为了方便”想读 `../../README.md`、`~/.ssh`、`/var/log`。但 agent 一旦能读这些地方，就可能把系统文件、密钥、配置都暴露出去。所以文件工具不能只靠 prompt 说“不要乱读”，必须在代码里硬拦。

**核心代码**：

```python
office_root = OFFICE_DIR.resolve()
candidate = (OFFICE_DIR / normalized).resolve()

if candidate != office_root and office_root not in candidate.parents:
    raise ValueError("path escapes the myClaw office sandbox")
```

**具体例子**：

office 根目录是：

```text
/Users/baiding/LightClaw/workspace/office
```

模型传：

```text
notes/a.txt
```

算出来是：

```text
/Users/baiding/LightClaw/workspace/office/notes/a.txt
```

这个路径还在 office 里面，放行。

模型传：

```text
../../README.md
```

`.resolve()` 会把 `..` 折叠掉，最后变成：

```text
/Users/baiding/LightClaw/README.md
```

这个路径已经跑出 office，拦截。

**为什么不用简单的 `startswith()`**：

因为字符串检查容易被边界情况绕过，尤其是软链接。比如 office 里有个链接指向 `~/.ssh`，表面路径看起来还在 office，真实目标已经出去了。`.resolve()` 会追到真实路径，再用 `candidate.parents` 判断父目录链，所以更稳。

**面试口语版**：

> 文件沙箱这块我没有只做字符串前缀判断，而是先用 `Path.resolve()` 把路径标准化，把 `..` 和软链接都摊平。然后看最终路径的父目录链里有没有 `workspace/office`。有就说明还在沙箱里，没有就说明越界了，直接拒绝。这样能挡路径穿越，也能挡软链接逃逸。

#### 2. Shell local backend：兼容模式，主要防误操作

**先讲人话版**：

local backend 是保留下来的兼容跑法：命令还是在本机跑，只是把工作目录固定到 `workspace/office/`，并且在执行前扫一遍命令字符串，发现明显危险的路径或提权命令就拒绝。

如果要走 local，可以这样配：

```bash
MYCLAW_SHELL_BACKEND=local
```

实际执行方式：

```python
subprocess.run(command, shell=True, cwd=str(OFFICE_DIR), timeout=60)
```

这层主要防几类明显危险操作：

```bash
cat /etc/passwd
ls ~
ls ../
sudo whoami
chmod 777 xxx
```

对应代码里有两组规则：

```python
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

**但是要诚实说清楚它的边界**：

local backend 不是完整 OS 沙箱。原因是：这个 shell 进程本质还是在宿主机上跑。`cwd=OFFICE_DIR` 只是说“默认从 office 目录启动”，不等于这个进程只能看到 office。

正则也只能看命令字符串里有没有危险字符。程序真正跑起来以后，可以动态做很多事，正则看不到。

比如：

```bash
# 可能读到父进程传下来的环境变量
python -c 'import os; print(os.environ)'

# 命令字符串里没写 "~"，但程序运行后自己问系统 home 在哪
python -c 'import pathlib; print(pathlib.Path.home())'

# 不用 curl，也能通过 Python 联网
python -c 'import urllib.request; print(urllib.request.urlopen("https://example.com").read()[:20])'

# 起一堆子进程，或者疯狂吃内存
python -c 'import subprocess; [subprocess.Popen(["sleep","60"]) for _ in range(1000)]'
```

所以 local backend 的定位很明确：**开发期、可信用户、防误操作、兼容旧流程**。它比裸 shell 安全，但不能拿来跑不可信代码。面试里不要把 local 说成真正 sandbox，真正的 shell sandbox 主线是下面的 Docker backend。

**面试口语版**：

> Shell local 这层我把命令固定在 office 目录启动，并且用正则拦 `../`、绝对路径、home 路径、sudo 这类明显危险命令。它主要是防模型误操作。但我不会把它说成真正沙箱，因为进程还是跑在宿主机上，正则只能看命令文本，挡不住脚本运行后动态读环境变量、联网、fork 子进程或者吃内存。所以它是基础保护，不是强隔离。

#### 3. Shell docker backend：当前 shell sandbox 的主线

**先讲人话版**：

现在强隔离的 shell sandbox 是基于 Docker 的。它把原来“在本机直接跑命令”，改成“开一个短生命周期容器，在容器里跑命令”。

这样脚本看到的是容器环境，不是完整宿主机。它能写的地方主要是挂进去的 `/workspace`，也就是本机的 `workspace/office/`。

开启方式：

```bash
MYCLAW_SHELL_BACKEND=docker
MYCLAW_DOCKER_IMAGE=python:3.12-slim
```

执行链路可以这样理解：

```text
原来：
agent -> execute_office_shell -> 本机 subprocess.run

现在：
agent -> execute_office_shell -> docker run -> 容器内 /bin/sh -lc command
```

当前 Docker 默认参数大概等价于：

```text
只挂载 office：  -v {OFFICE_DIR}:/workspace:rw
工作目录：       -w /workspace
默认禁网：       --network none
根文件系统只读： --read-only
限制资源：       --memory 512m --cpus 1 --pids-limit 128
降低权限：       --cap-drop ALL --security-opt no-new-privileges
临时目录：       --tmpfs /tmp:rw,nosuid,nodev,size=64m
```

这几个参数分别解决什么问题：

- 只挂 `office`：模型看不到整个项目和用户 home，只能操作给它的工作目录。
- 默认禁网：脚本里用 Python/Node 联网也出不去。
- 根文件系统只读：容器系统目录不能随便改。
- 限 CPU/内存/进程：防止一个脚本把机器资源打满。
- 降低权限：减少容器里提权或做危险系统操作的空间。

举个例子：

```bash
python -c 'open("/etc/passwd").read()'
```

在 local backend 里，这种命令如果绕过了正则，就可能碰到宿主机文件。

在 Docker backend 里，就算能执行，读到的也是容器自己的 `/etc/passwd`，不是你的 macOS/Linux 宿主机文件。

再比如：

```bash
python -c 'import urllib.request; urllib.request.urlopen("https://example.com")'
```

Docker backend 默认 `--network none`，所以脚本出不了网。

可调参数：

```bash
MYCLAW_DOCKER_IMAGE=python:3.12-slim
MYCLAW_DOCKER_PULL=missing
MYCLAW_DOCKER_NETWORK=none
MYCLAW_DOCKER_MEMORY=512m
MYCLAW_DOCKER_CPUS=1
MYCLAW_DOCKER_PIDS=128
```

**也要说明限制**：

Docker 不是 VM。它还是共享宿主机 kernel，所以不是 Firecracker/Kata 那种更强的虚拟机级隔离。但对 LightClaw 当前阶段来说，Docker 已经把 shell 的安全边界从“正则检查命令字符串”，升级成了“运行时限制文件系统、网络和资源”。

**面试口语版**：

> 现在 shell sandbox 的强隔离版本是基于 Docker 的。我不再让模型生成的命令直接跑在宿主机上，而是每次起一个短生命周期容器。容器只挂载 `workspace/office` 到 `/workspace`，默认禁网，根文件系统只读，并限制 CPU、内存和进程数。这样即使模型运行了 Python 脚本，脚本看到的也是容器环境，不是用户真实机器。它不是 VM 级隔离，但已经比 local backend 强很多。

#### 4. 超时和非交互检测：防止命令卡死

**先讲人话版**：

模型有时候会执行需要人工输入的命令，比如进入 Python REPL、跑一个等确认的安装命令，或者启动一个一直不退出的服务。如果不管它，agent 这一轮就会卡住。

所以 shell 工具统一加了 60 秒超时：

```python
SHELL_TIMEOUT = 60
subprocess.run(..., timeout=SHELL_TIMEOUT)
```

如果返回里像是在等确认，也会提示模型加 `-y` 或 `--yes`：

```python
if result.returncode != 0 and ("prompt" in stderr.lower() or "y/n" in stdout.lower()):
    output += "\nHint: Command may require confirmation. Use -y or --yes flags."
```

**面试口语版**：

> Shell 工具我不允许它无限跑。每条命令都有 60 秒 timeout，超时就熔断。另外如果错误输出看起来像在等确认，比如 `y/n` 或 prompt，就提示模型下次用非交互参数。这个主要是防 agent 被一个挂住的 shell 命令拖死。

#### 5. 当前沙箱分层：面试时可以这样讲

**一句话总览**：

> 我这套 sandbox 是分层做的。文件读写靠路径解析做硬边界；shell 的强隔离版本基于 Docker，把命令放进受限容器里跑，默认禁网、只挂 office、限制资源；local shell 只是兼容和开发调试用的防误操作模式；再外面还有 ToolGate 做权限判断，决定哪些工具能不能执行、要不要问用户。

**展开版**：

- 文件工具：`Path.resolve()` 把路径摊平，再检查最终路径是否还在 `workspace/office`。
- Shell docker：当前强隔离 shell sandbox，命令进容器，默认禁网，只挂 office，限制 CPU/内存/进程。
- Shell local：兼容/开发模式，命令从 office 启动，执行前拦 `../`、`/etc`、`~`、`sudo` 这类明显危险输入。
- ToolGate：工具执行前做策略判断，高风险操作可以 DENY 或 ASK。
- Trace：每次工具调用和 gate 决策都会记录，方便复盘。

如果被问："为什么有了正则还要 Docker？"

回答：

> 因为正则只能看命令文本，拦的是显眼的危险写法。脚本真正跑起来以后，可以动态构造路径、读环境变量、联网、开子进程、吃内存，这些不是正则能完整挡住的。Docker 是运行时边界，它从文件系统、网络和资源层面限制进程。所以 local backend 是防误操作，docker backend 才更接近真正的 sandbox。

如果被问："Docker 会不会很麻烦？"

回答：

> 起容器本身不复杂，真正麻烦的是镜像和依赖。所以第一阶段先用 `python:3.12-slim` 跑普通 shell；镜像本地有的话，`docker run --rm` 就是短生命周期执行。后面可以预构建一个 `lightclaw-sandbox` 镜像，把 Python、Node、rg、git 这些常用工具提前装好，避免每次任务临时安装。

#### 6. 计算器安全 eval（已有）

**为什么需要**：原生 `eval(expression)` 会执行任意 Python 表达式。如果大模型接收到恶意输入计算 `__import__('os').system('rm -rf /')`，整个系统就被攻破了。

**具体 case**：用户让 AI"帮我计算一下这个表达式的值"，恶意对手通过提示词注入让它计算 `open('/etc/passwd').read()`——没有沙盒的话能直接读系统文件。

```python
# builtins.py
result = eval(expression, {"__builtins__": {}}, {})
```

清空 `__builtins__` 可以阻止一切系统内置函数的调用，**仅保留基础数学运算**。✅ LightClaw 已有。

---

### 19. Skill 懒加载：渐进式披露 vs 原生懒加载

**原生 Skill 渐进式披露（CyberClaw）**：

传统方式：AI 看到所有 skill 的 description，然后直接选一个调用。但 description 再长也是摘要，可能选错。

CyberClaw 的两阶段：

- 第一阶段：AI 看到 skill 名字 + 摘要描述，决定“我要用这个”。
- 第二阶段：AI 读完整的 `SKILL.md` 说明书，再决定“具体怎么用”。

如果读完后发现不对，可以换别的 skill，不会有决策撤回的风险。

**LightClaw 的懒加载**：

- 扫描阶段：只读文件夹名 + `SKILL.md` 前 50 行提取 `name/description`。
- 首次调用：`mode=help` 时才真正读完整 `SKILL.md`，缓存 60 秒。
- 执行阶段：`mode=run` 执行具体命令。

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

### 20. LRU 缓存机制（轻量扫描/首次加载/缓存失效）

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

### 21. 未做的 Harness 约束（待实现）

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

### 22. 隐式记忆问题：工具名倒推的漏洞和修复方向

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

### 23. 为什么简单替换不够：分层处理和状态恢复

**面试里可以这么说**：

> 我现在的 completion hook 能兜住一个很重要的问题：工具失败了，但 AI 还说"已完成"。这个必须拦，因为不能让用户拿到假的成功反馈。
> 
> 但从产品体验和系统可靠性上看，简单替换还不够。因为失败不是一种东西。网络超时、429、参数缺失、权限不足、磁盘满、上下文超限、模型幻觉说成功，这些处理方式都不应该一样。
> 
> 所以更合理的方向是分层：能重试的自动重试，能让模型修正的把错误回灌给模型，需要用户介入的讲清楚原因，完全不可恢复的就诚实失败。不能所有错误都粗暴变成一句"操作失败"。

**具体 case**：

| 失败类型                | 当前行为                    | 用户体验                                      |
| ------------------- | ----------------------- | ----------------------------------------- |
| 网络超时、429、503        | LLM 层已有有限 retry，工具层还不完整 | 这类通常可以再试一次，不应该立刻判死刑                       |
| 工具参数缺失              | 返回 error observation    | 模型下一轮可以看到错误，有机会补参数                        |
| 工具返回 error 但 AI 说成功 | completion hook 替换回复    | 这个兜底是必要的，不能让用户收到假成功                       |
| 文件权限不够、磁盘满          | 目前主要暴露失败文本              | 应该讲清楚用户要改权限、清空间，还是换路径                     |
| 上下文太长               | context guard 调用前压缩     | 后续还可以捕获 provider context-too-long 后二次压缩重试 |
| 进程或流式解析失败           | 前端收到 stream_error       | 用户知道不是卡死，开发者能查 trace                      |

**可以参考的成熟做法**：

1. **LangGraph**
   
   它更像图状态机。每个节点可以有 retry、timeout、error handler，checkpoint 也更完整。失败后可以从最后的状态继续，而不是整轮重跑。

2. **Temporal**
   
   它把外部动作放到 Activity 里，每个 Activity 可以声明 retry policy，比如最多几次、退避多久、哪些错误不能重试。它特别强调幂等，因为重试一个有副作用的动作很危险。

3. **OpenAI Agents SDK / Claude Code 这类 agent runtime**
   
   重点不是一出错就替换，而是让工具结果、guardrail、trace 都进入上下文和观测链路。模型能感知失败就让它修正；模型反复忽略事实或者声称成功时，再由 guardrail/hook 兜底。

**更完善的做法**：

```python
# 按失败类型分层处理
if error.retryable and operation.idempotent:
    return retry_with_backoff_and_jitter()
elif error.kind == "validation":
    return return_observation_for_llm_to_fix_args()
elif tool_failed and answer_claims_success:
    return replace_with_fact(tool_result)
elif error.requires_user_action:
    return explain_action_to_user(error)
else:
    return honest_failure(error)
```

**当前已经做了什么**：

- LLM/provider 瞬时错误有限 retry
- 工具失败转成 observation，不让 agent loop 崩
- 工具结果分类成 `ok/error/unchanged/denied`
- completion hook 拦截"失败后说成功"
- context guard 做调用前压缩
- checkpoint 和 stream_error 让失败可观测

**当前还没做完整的部分**：

- retry 没有 jitter、最大延迟和结构化 retry trace
- 工具级 retry 还没按幂等性开放
- 没有 fallback model
- checkpoint 还不是完整 `AgentState` 快照，不能真正从中间 resume
- 没有 request_id / idempotency key，前端重复发送可能带来重复副作用
- 没有 per-session lock，同一 session 并发 turn 可能互相污染状态

**口语版总结**：

> 我现在做的是第一阶段可靠性：失败不要静默、不要把进程打崩、不要让 AI 假装成功，并且每一步都能从 trace 里查到。下一阶段才是生产级可靠性，比如对只读工具做有限 retry、写操作加 idempotency key、同一个 session 加锁、provider 连续失败时切 fallback model，再把 checkpoint 从"记录状态"升级成"能恢复状态"。

---

### 24. 评测方法：怎么证明 Harness 真的变好了

评测模块解决的是“我们怎么知道 harness 真的变好了，而不是感觉变好了”。我会按三层讲：

1. **确定性单元测试**：直接测工具、状态、沙盒、缓存、任务这些纯工程逻辑。
2. **ReAct loop 测试**：用 fake/queued model 模拟模型输出，检查 tool call、observation、max_turns、gate trace 是否按预期流动。
3. **Trace / badcase eval**：把真实交互中的问题固化成 eval，后续每改一次 harness 都能回放检查。

**测试覆盖矩阵**：

| 测试文件                                                       | 覆盖            | 测试重点                                           |
| ---------------------------------------------------------- | ------------- | ---------------------------------------------- |
| `test_agent.py` / `test_mvp_learning.py`                   | Agent loop    | tool call 是否执行、observation 是否回灌、max_turns 是否兜底 |
| `test_policy.py`                                           | ToolGate      | `off/default/plan/auto`、硬安全 deny、用户授权后 allow   |
| `test_memory_routing.py`                                   | Memory scope  | profile/note/session 分类、临时信息不写长期               |
| `test_context_advanced.py` / `test_harness_reliability.py` | Context guard | 长工具结果压缩、历史 trim、tool metadata 更新               |
| `test_sandbox_tools_migrated.py` / `test_constraints.py`   | 沙盒            | 路径穿越、绝对路径、home、危险 shell、超时                     |
| `test_skill_loader.py` / `test_lazy_loader_migrated.py`    | Skill 懒加载     | metadata 扫描、help 首次加载、缓存失效、run 参数校验            |
| `test_two_phase_skills.py`                                 | 两阶段 skill     | 陷阱工具 vs 正确工具，help→run 是否降低误用                   |
| `test_heartbeat.py`                                        | 定时任务          | 一次性任务、循环任务、非法时间、月末边界                           |
| `test_memory_policy_suite.py`                              | Trace badcase | memory/policy 问题能否从 trace 回放验证                 |

**两阶段安全评测怎么讲**：

两阶段测试会构造“陷阱工具”和“正确工具”。陷阱工具的名字和简介看起来很像能解决问题，但完整 manual 里写着禁用条件；正确工具简介可能没那么显眼，但 manual 说明它才适用。单阶段容易望文生义直接 run 陷阱工具；两阶段强制先 help，看完说明书再 run。

| 指标      | 单阶段   | 两阶段          | 含义            |
| ------- | ----- | ------------ | ------------- |
| 安全命中率   | 约 50% | 约 90%        | 最终是否选对工具      |
| P0 级事故率 | 约 50% | 约 10%        | 是否执行明显错误或危险工具 |
| 平均决策耗时  | 较低    | 增加一次 help 成本 | 用延迟换安全        |

这组评测的重点不是“回答像不像”，而是“中间过程是否安全”。如果 help 成本增加 20% 左右，但危险工具执行率明显下降，这个 tradeoff 是可以解释的。

**Badcase eval 的工作流**：

```text
真实交互发现问题
  -> 保存 JSONL trace
  -> 从 trace 提取输入、工具调用、gate 决策、最终回答
  -> 写成 eval case
  -> 修改 harness
  -> 重新执行 case，生成新 trace
  -> 对比是否仍然误写记忆、误联网、误报成功
```

口语版可以这么答：

> 我不会只说“我加了测试”，而是按风险面测。工具和沙盒是确定性测试，ReAct loop 用 fake model 测链路，memory/policy badcase 用 trace 回放测真实行为。每次发现问题先固化成 eval，再改 harness，最后重新跑 eval 看问题有没有消失、有没有引入新问题。

**为什么先迁移确定性 harness 测试，而不是一上来跑真实 LLM 大评测**：

`test-migration-results.md` 里记录的思路是：先把 CyberClaw 里可确定、可回归的机制测试迁移过来，比如 skill loader、context trimming、sandbox tools、two-phase skills、heartbeat、trace/logger。这样做的收益是测试稳定，不受模型随机性影响，适合先验证 harness 本身有没有退化。

真实模型评测也重要，但它应该放在第二层：当工具、权限、记忆、上下文这些底座稳定后，再用真实 LLM 看行为分布。否则模型偶然答对/答错会掩盖工程机制问题。

可以这样总结取舍：

| 阶段                  | 测什么                                   | 优点         | 缺点                  |
| ------------------- | ------------------------------------- | ---------- | ------------------- |
| 确定性 harness 测试      | 工具、policy、memory、context、skill loader | 稳定、快、适合 CI | 不代表真实模型一定会这么用       |
| Fake model ReAct 测试 | 指定 tool call 序列下 loop 是否正确            | 能测链路和状态    | 不测模型选择能力            |
| 真实 LLM eval         | 模型在约束下是否选对工具、是否遵守规则                   | 最接近真实使用    | 成本高、波动大、需要 trace 判分 |
| Trace badcase 回放    | 历史问题是否复现/修复                           | 能形成迭代闭环    | 需要持续维护 case         |

---

### 25. Agent 完整跑一圈：结合 Harness 设计详解

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
- `mode=default` 或 `mode=auto` → 返回 ASK + "paused by policy"
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

---

### 26. 简历讲法、真实场景和速记卡片

这部分是面试收尾用的：把前面的技术点压缩成业务价值和工程价值。

**一句话定位**：

> LightClaw 是一个透明可控的 Agent Harness：模型可以用工具做事，但每一步输入、工具调用、权限判断、工具结果、失败兜底和最终回答都可观测、可拦截、可评测。

**简历 bullet 可以这么写**：

- 实现原生 ReAct Agent Runtime，支持多轮 tool call、observation 回灌、max_turns 兜底、工具异常恢复，并将每个推理轮次记录为可回放 trace。
- 构建记忆与上下文管理系统，将短期 session、长期 user profile、项目 note、自动摘要和 token 预算结合起来，解决长对话遗忘、污染和上下文爆炸问题。
- 设计 ToolGate 权限模型，在工具执行前根据资源类型、作用域、风险等级和运行模式给出 allow / ask / deny 决策，并在客户端展示授权过程。
- 引入 Skill 懒加载和 help→run 两阶段执行，先读取技能元信息，真正需要时再展开完整说明，降低 prompt 压力和危险工具误用率。
- 建立 badcase 驱动的评测闭环，把真实交互中的记忆误写、错误联网、工具误用、失败后说成功等问题固化为 eval。

**技术栈速记**：

| 模块         | 技术/实现                                                   |
| ---------- | ------------------------------------------------------- |
| Agent loop | Python 原生 ReAct while loop                              |
| LLM        | OpenAI / Anthropic 兼容 LangChain chat model              |
| 工具         | `@tool` + `BaseTool/FunctionTool`                       |
| 存储         | Markdown profile/note + JSON session/task + JSONL trace |
| 客户端        | Tauri + React + Vite                                    |
| 并发         | 心跳队列、任务文件锁、流式事件                                         |
| 安全         | ToolGate、文件 sandbox、shell 正则拦截、completion hook          |

**真实场景怎么串起来**：

一个适合深入讲的场景是“简历与作品集生成助手”。用户说：

> 帮我基于最近项目经历生成一版 Agent 方向简历，并把关键项目整理成作品集说明。

完整链路：

1. 读取长期 profile，拿到教育背景、技术栈、表达偏好和目标岗位。
2. 读取项目 notes、workspace 文件和必要 trace，找到真实做过的模块。
3. 长材料先过 context guard 或摘要策略，避免 prompt 爆掉。
4. 选择简历/文档/PPT skill，必要时 help→run 两阶段确认。
5. 生成 `resume.md`、项目介绍文档或 PPT 大纲。
6. 文件写入前经过 ToolGate，确认路径在 office sandbox 内。
7. 用户修改偏好后，写入长期 profile 或项目 note。
8. 整个过程写成 trace，后续可以回放或转成 eval case。

**面试官可能追问**：

**Q: 这个项目和普通 RAG / 聊天机器人有什么区别？**

> 普通聊天机器人重点是回答，RAG 重点是检索增强；LightClaw 重点是 agent runtime 治理。它不只关心“回答是什么”，还关心回答之前发生了什么：上下文怎么构造，工具怎么选，权限怎么判，文件有没有越权，失败怎么恢复，trace 怎么复盘，badcase 怎么变成评测。

**Q: 你觉得最有技术含量的地方是什么？**

> 不是某一个工具，而是把模型的不稳定行为放进一个可控 harness 里。记忆写入不能靠一句“请记住”，要有 scope 判断、工具权限、落盘和 eval；工具调用不能只靠 prompt，要有 ToolGate 和沙盒；上下文不能无限塞，要有摘要和 token 预算；每次问题修完都要固化成 badcase。

**Q: 如果要产品化，下一步补什么？**

> 第一是把权限策略从规则升级成可配置策略，包括资源、用户、环境和风险等级；第二是把 eval 做成持续回归，每次改 harness 都自动跑 agent 级 case；第三是把 skill / MCP 生态打通，但所有外部能力都必须经过同一套权限、trace 和评测系统。

**产品化权限应该分层，而不是只看单次 tool call**：

| 层级              | 解决的问题                               |
| --------------- | ----------------------------------- |
| Agent 可见工具      | 这个 agent 有没有资格看到某类工具                |
| Session 可用工具    | 当前会话是否临时禁用联网、shell、写文件              |
| Resource/action | 能不能对某类资源执行 read/write/search/delete |
| 参数级权限           | 这个路径、URL、命令、note_id 是否安全            |
| Sandbox 硬边界     | 即使策略放行，工具也不能越过运行时边界                 |
| Trace / eval    | 每次放行或拒绝都能复盘，并固化成回归测试                |

这也是从 OpenClaw/Claude Code 类系统得到的启发：工具可见性、运行环境、用户确认、hook relay 和审计事件应该分层设计。LightClaw 当前先做了统一 ToolGate 和 sandbox，后续可以把“哪些工具可见”和“哪些资源可写”也配置化。
