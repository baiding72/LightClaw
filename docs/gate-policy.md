# myClaw Gate Policy 设计笔记

这份文档记录当前 myClaw 的工具权限系统。它的目标不是让模型“更听话”，而是在模型想调用工具和工具真正执行之间，加一层稳定、可观察、可逐步增强的控制点。

## 当前实现

模型产生工具调用后，不会直接执行工具，而是先进入 `ToolPolicy`。

流程是：

```text
模型决定调用工具
  -> AgentHarness 收到 tool_call
  -> ToolPolicy 判断资源、动作、风险
  -> 得到 allow / ask / deny
  -> 写入 trace
  -> allow 才执行工具
  -> ask 会等待前端确认
  -> deny 或确认超时则不执行工具
```

关键代码：

- `myClaw/core/policy.py`
- `myClaw/core/agent.py`
- `myClaw/interactive_turn.py`
- `client/src/main.tsx`
- `client/src-tauri/src/main.rs`

## 三种结果

`ToolGateDecision` 有三种：

- `allow`：允许执行工具。
- `ask`：需要用户确认。
- `deny`：不执行工具。

现在 `deny` 主要来自用户拒绝或确认超时；后续可以加入更强的禁止策略，比如路径越权、危险命令、不可逆删除等。

## 三种模式

当前配置放在：

```text
myClaw/config/policy.json
```

默认是：

```json
{
  "mode": "off",
  "approval_timeout_seconds": 300
}
```

模式含义：

- `off`：关闭权限观察和拦截。工具照常执行，不写 `tool_gate_decision`。默认使用这个，避免学习阶段被频繁弹窗和额外 trace 打断。
- `monitor`：工具照常执行，但会写 `tool_gate_decision`。适合收集 badcase，观察模型会不会乱写记忆、乱联网、乱改文件。
- `enforce`：会写 `tool_gate_decision`，并且遇到高风险工具时弹窗确认。用户允许后继续执行，拒绝或超时就不执行。

所以这三个模式的区别应该是：

```text
off      = 不看、不记、不拦
monitor  = 看见、记录、不拦
enforce  = 看见、记录、会拦
```

前端设置按钮里可以切换这三个模式。

## 工具如何映射成权限

我们没有只按工具名写一堆特殊判断，而是先把工具翻译成“资源 + 动作”。

例如：

```text
save_note             -> memory.note:create
update_note           -> memory.note:update
search_notes          -> memory.note:search
read_note             -> memory.note:read

save_user_profile     -> memory.profile:create
update_user_profile   -> memory.profile:update
read_user_profile     -> memory.profile:read

write_office_file     -> office.file:create
update_office_file    -> office.file:update
read_office_file      -> office.file:read

web_search            -> external.web:search
read_url              -> external.web:read
```

这样后续讨论权限时，就不是“这个工具名要不要禁”，而是：

- 能不能写长期画像？
- 能不能写项目文件？
- 能不能访问外部网络？
- 能不能更新已有笔记？

这个抽象比 prompt 里的几句话更稳。

## ask 是怎么等待前端的

`enforce` 模式下，如果一个工具需要确认，后端会发出 `tool_gate_decision` 事件。

前端收到事件后弹窗，展示：

- 工具名
- 工具参数
- 权限类型
- 风险等级
- 记忆范围判断
- 来源判断
- 为什么需要确认

用户点击“允许执行”后，前端调用：

```text
submit_tool_gate_decision
```

Tauri 会把结果写到：

```text
myClaw/runtime/approvals/<request_id>.json
```

Python 侧正在等待这个文件。看到允许后继续执行工具；看到拒绝或超时就返回一个工具未执行的 observation，ReAct loop 不会直接越过用户确认。

这是一个本地文件桥接方案，好处是简单、可调试、trace 清楚。后面如果要更工程化，可以换成更正式的双向事件通道。

## CyberClaw 的 memory scope 做法

CyberClaw 当前不是用独立的 memory scope 分类器来做判断，而是靠两层约束：

1. 每轮都会读取 `memory/user_profile.md`，把长期用户画像注入系统提示。
2. 对旧上下文做摘要时，明确要求摘要只记录“当前聊什么、解决了什么、任务进度”，不要记录用户静态偏好。

也就是说，CyberClaw 的思路是：

```text
长期画像：user_profile.md
近期上下文：summary
具体判断：主要靠 prompt 和 save_user_profile 工具说明
```

这很适合 MVP，因为实现简单，也容易观察效果。但它的问题是：模型偶尔会把“临时偏好”写进长期画像，或者该写的时候没写。

## myClaw 的 memory scope 设计

myClaw 现在加了一个轻量判断器：

```text
myClaw/core/memory_scope.py
```

它会把用户输入粗分成：

- `session`：临时、当前会话、本轮有效的信息。
- `profile`：长期用户偏好、回答风格、个人画像。
- `note`：项目知识、badcase、设计记录、可检索资料。
- `none`：不是记忆写入。

这个判断结果不会直接替代模型，而是写进 gate trace。

现在 trace 里不只记录一个 scope，还会记录更结构化的信息：

```text
memory_scope
memory_scope_confidence
memory_intent          # write / update / none
memory_persistence     # current_session / cross_session / searchable
memory_subject         # conversation / user_profile / project_or_note
memory_signals         # 命中的判断信号
```

这样我们调 badcase 时看到的不只是“模型写了 profile”，还能看到 harness 认为这次写入到底像临时会话、长期画像，还是项目笔记。

如果进入 `enforce` 模式，且出现明显不匹配，比如：

```text
用户说“临时偏好”
模型却调用 save_user_profile
```

系统会倾向于弹窗确认，而不是默默写入长期画像。

### memory scope 具体怎么判断

现在这版判断非常朴素，先不要把它理解成“智能记忆系统”。它更像一个交通灯：看用户这句话里有没有明显信号，再结合模型准备调用的工具，给出一个可记录、可评测的判断。

它大概按这个顺序看：

1. **先看是不是临时信息。**

   只要用户话里出现这类词：

   ```text
   临时、当前会话、这次会话、本轮、先暂时、现在先、temporary
   ```

   harness 就会先判成 `session`。

   例如：

   ```text
   这次会话里先用简短回答。
   当前会话临时记一下这个代号。
   ```

   这类信息不应该直接写进长期 profile。哪怕模型调用了 `save_user_profile`，policy 也会认为“这里可能不对”，在 `enforce` 模式下要求确认。

2. **再看模型想写的是不是用户画像。**

   如果模型准备调用：

   ```text
   save_user_profile
   update_user_profile
   ```

   harness 会看用户话里有没有长期偏好的信号：

   ```text
   以后、我喜欢、我更喜欢、我的偏好、个人偏好、回答风格、请记住、记住：
   ```

   如果有，就判成 `profile`，意思是“这像跨 session 都要生效的长期用户画像”。

   例如：

   ```text
   请记住，我更喜欢你用中文回答。
   以后解释代码时先讲整体思路。
   ```

3. **再看模型想写的是不是笔记。**

   如果模型准备调用：

   ```text
   save_note
   update_note
   ```

   harness 会看用户话里有没有项目知识或可检索资料的信号：

   ```text
   badcase、项目、设计、规范、记录、文档、方案、计划、总结
   ```

   如果有，就判成 `note`。

   例如：

   ```text
   把这个 badcase 记录下来。
   总结一下 memory 系统三阶段设计。
   ```

4. **再额外判断这次像新写入还是更新。**

   如果用户说：

   ```text
   更新、修改、补充、修正、改成、追加
   ```

   `memory_intent` 会是 `update`。

   如果用户说：

   ```text
   记住、记录、保存、写入、以后、总结一下、整理
   ```

   `memory_intent` 会是 `write`。

   这个字段目前主要用于 trace 和 eval，后面可以用来约束“第一次用 save，后续用 update”。

5. **如果没有明显信号，就降低置信度。**

   比如模型调用了 `save_user_profile`，但用户没有说“以后”“我喜欢”“请记住”这类词，harness 仍然会知道工具目标是 profile，但置信度只有 `0.55`。

   这代表：“模型想写长期画像，但用户语义不够明确。”

这套规则的重点不是一次就判断得完美，而是让 badcase 能被看见。以前我们只能看到“模型写了 profile”，现在能看到：

```text
模型写了 profile
但用户表达像 session
命中了“当前会话/临时”
所以这次写入应该被确认或阻止
```

这就是 harness 约束比 prompt 更有价值的地方：它把模糊行为变成了可检查字段。

## source routing 设计

source routing 解决的是：什么时候应该联网，什么时候应该先查本地。

现在新增了：

```text
myClaw/core/source_routing.py
myClaw/core/local_retrieval.py
myClaw/core/tools/local.py
```

它会对联网工具做一个来源判断：

- `network_candidate`：问题带有实时、官网、网页、新闻、价格、最新等信号，可能需要联网。
- `local_first`：问题明显指向当前项目、当前会话、trace、workspace、myClaw 本地资料，应先查本地。
- `unclear`：信号不足。

和上一版不同，现在 `local_first` 不是只打标签。source routing 会先调用本地检索，搜索：

- `~/.myclaw/profile.md`
- `~/.myclaw/notes/*.json`
- `workspace/office/`
- `myClaw/docs/`
- `runs/*.jsonl`

如果找到候选来源，会把 `local_source_hits` 写进 gate trace。Agent 也新增了 `search_local_sources` 工具，模型可以在回答本地项目、trace、历史记录问题时先查本地，而不是直接联网。

### routing 策略具体怎么定

routing 现在只在模型准备调用联网工具时触发，也就是：

```text
web_search
read_url
```

如果模型调用的是读文件、查 note、算数、任务工具，那 source routing 会直接返回 `not_network_tool`。

对于联网工具，它会做三件事。

1. **数一数“需要外部信息”的信号。**

   这类词会增加 `freshness_score`：

   ```text
   最新、今天、现在、实时、新闻、价格、官网、网页、互联网、搜索、查一下、浏览
   today、latest、current、当前年份
   ```

   这些词说明用户可能真的需要外部世界的信息。

   例如：

   ```text
   查一下今天的比特币价格。
   看看官网最新文档怎么说。
   ```

   这类问题更可能被判成 `network_candidate`。

2. **数一数“应该先看本地”的信号。**

   这类词会增加 `local_score`：

   ```text
   myClaw、CyberClaw、当前项目、这个项目、本项目、trace、前面、刚才、会话、workspace
   ```

   这些词说明用户问的不是互联网，而是本地项目、历史轨迹、当前会话或 workspace。

   例如：

   ```text
   myClaw 现在的 gate policy 是怎么实现的？
   看一下刚才那条 trace 为什么没写入 profile。
   ```

   这类问题应该先查本地。

3. **真的跑一遍本地检索。**

   routing 不只看关键词，还会用用户问题去搜本地资料：

   ```text
   profile
   notes
   office files
   docs
   runs trace
   ```

   如果搜到了候选内容，即使用户没有特别明显地说“本地”，也会倾向 `local_first`。

最后的决策逻辑很简单：

```text
如果外部信号分数 > 本地信号分数：
    network_candidate
否则如果有本地信号，或者本地检索搜到了东西：
    local_first
否则：
    unclear
```

几个例子：

```text
“查一下 OpenAI 官网最新 Responses API 文档”
-> freshness_score 高
-> network_candidate

“myClaw 的 memory scope 是怎么判断的”
-> local_score 高，并且 docs/code 里能搜到
-> local_first

“这个错误是什么意思”
-> 外部信号和本地信号都不明显
-> unclear
```

这里有一个刻意的设计：`local_first` 不是“永远不联网”。它的意思是“先查本地，如果本地不够，再考虑联网”。这比“默认禁 web”更灵活，也比“模型想搜就搜”更可控。

当前局限也很明确：

- 关键词还是手写规则。
- 本地检索是轻量文本匹配，不是 embedding 检索。
- 还没有把 `local_first` 强制改写成先调用 `search_local_sources`。
- 还没有在最终回答里强制列出 sources。

但这版已经足够支持下一轮 eval：我们可以专门测试“问本地项目时是否先查本地”和“问最新官网时是否允许联网”。

## 这是 hook 吗

是，可以把它理解成 `before_tool_execute` hook。

更口语化地说：模型并不是直接拿到工具就能执行。每次模型想调用工具时，myClaw 会在“工具真正执行前”插一段代码，先问一句：

```text
这个工具调用现在能不能执行？
```

这段插进去的代码就是 hook。它做的事情是：

```text
模型产生 tool_call
  -> harness 捕获 tool_call
  -> 进入 ToolPolicy
  -> 判断 memory scope / source routing / 权限风险
  -> 得到 allow / ask / deny
  -> allow 才真正 tool.invoke()
```

核心入口在 `AgentHarness._execute_tool`：

```python
context = ToolGateContext(
    tool_name=tool_name,
    args=args,
    user_input=user_input,
    react_step=react_step,
)

gate = self.tool_policy.evaluate(context)

if gate.decision != ToolGateDecision.ALLOW:
    return (
        f"Tool execution paused by policy: {gate.decision.value}. "
        f"Permission={gate.permission.key}. Reason={gate.reason}",
        gate,
    )

result = tool.invoke(**clean_args)
```

真正的硬拦截就在这里：

```python
if gate.decision != ToolGateDecision.ALLOW:
    return ...
```

只要不是 `allow`，就不会走到 `tool.invoke()`。

## 它是不是通过事件实现的

一半是，一半不是。

**真正的拦截不是靠事件。**

真正的拦截靠 `_execute_tool()` 里的同步代码判断。也就是：

```text
policy 不允许 -> 函数直接返回 -> 工具不执行
```

**事件负责通知前端和记录 trace。**

在 streaming 客户端里，如果 policy 返回 `ask`，Python 会发出一条 `tool_gate_decision` 事件：

```python
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
```

前端监听这个事件：

```tsx
listen("tool_gate_decision", (event) => {
  if (payload.tool_gate_decision === "ask" && payload.request_id) {
    setPendingToolGate(...)
  }
})
```

用户点击允许或拒绝后，前端调用：

```text
submit_tool_gate_decision
```

Tauri 把结果写到：

```text
myClaw/runtime/approvals/<request_id>.json
```

Python 侧轮询这个文件：

```python
while time.time() < deadline:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("decision", "")).lower() == "allow"
    time.sleep(0.2)
```

所以这条链路可以分成两层：

```text
hook/policy 层：决定能不能执行，是真正的执行边界
event/UI 层：通知用户、等待确认、记录 trace
```

事件不应该被理解成安全边界。事件只是传话和观测。真正的边界是“没有 allow 就不调用工具”。

## 这套机制的核心代码

当前核心文件是：

```text
myClaw/core/agent.py
myClaw/core/policy.py
myClaw/core/memory_scope.py
myClaw/core/source_routing.py
myClaw/interactive_turn.py
client/src/main.tsx
client/src-tauri/src/main.rs
```

最小链路是：

```text
AgentHarness.stream()
  -> yield tool_call
  -> _execute_tool()
  -> ToolPolicy.evaluate()
  -> infer_memory_scope()
  -> infer_source_route()
  -> allow/ask/deny
  -> emit tool_gate_decision
  -> frontend approval modal
  -> submit_tool_gate_decision
  -> approval file
  -> tool.invoke()
```

如果只看后端，核心代码关系是：

```text
agent.py::_execute_tool
  调用 policy.py::ToolPolicy.evaluate
    调用 memory_scope.py::infer_memory_scope
    调用 source_routing.py::infer_source_route
  如果 decision != allow，直接返回，不执行工具
```

如果看前端确认，核心代码关系是：

```text
interactive_turn.py::wait_for_tool_approval
  emit_event("tool_gate_decision")
  等待 approvals/<request_id>.json

main.tsx
  listen("tool_gate_decision")
  弹确认框
  调 submit_tool_gate_decision

main.rs::submit_tool_gate_decision
  写 approvals/<request_id>.json
```

## CyberClaw 有没有做这部分约束

本地 CyberClaw 做了几类约束，但没有 myClaw 现在这种统一的 tool gate hook。

### CyberClaw 有的

1. **工具沙盒硬边界**

文件工具会走 `_get_safe_path()`，把路径限制在 `office` 工位内。模型传 `../../etc/passwd` 会被拦。

Shell 工具固定 `cwd=OFFICE_DIR`，并用正则拦截：

```text
..
/absolute path
~
\ Windows root
C: Windows drive
```

2. **工具说明里的软约束**

比如 shell 工具说明里写：

```text
禁止 cd 跳出当前目录
禁止访问 office 外部
非交互式命令要带 -y
```

这些是给模型看的，不是所有都由代码强制。

3. **LangGraph 的工具节点**

CyberClaw 用的是：

```python
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(actual_tools))
workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")
```

也就是说，模型输出 tool call 后，LangGraph 的 `ToolNode` 负责执行工具。

4. **审计日志**

CyberClaw 会记录：

```text
llm_input
tool_call
tool_result
ai_message
```

这能看到模型做了什么，但不是执行前拦截。

5. **两阶段 skill**

动态 skill 是 `mode='help'` / `mode='run'`。第一次应该先看完整说明书，再决定是否执行。这是一种“先观察再执行”的软硬混合约束。

### CyberClaw 没有的

从本地代码看，它没有这些：

```text
ToolGateDecision = allow / ask / deny
统一 ToolPolicy.evaluate()
memory scope 判断
source routing 判断
前端 approval modal
工具执行前 ask 并暂停 loop
```

所以 CyberClaw 的主要思路是：

```text
工具自身做沙盒硬边界
prompt/docstring 做行为约束
trace 做透明审计
help/run 做技能误用降低
```

myClaw 现在多加的是：

```text
工具执行前统一 gate
```

这正是我们为了学习 harness 调优额外补的一层。

## OpenClaw 类系统是怎么做的

这里说的是公开 OpenClaw 文档里的设计，不是本地代码。

OpenClaw 的权限模型更接近多层控制：

1. **Agent 级工具 allow/deny**

每个 agent 可以配置自己能看到/能用哪些工具。

类似：

```text
agents.list[].tools.allow
agents.list[].tools.deny
```

这解决的是：“这个 agent 有没有资格用这个工具。”

2. **Sandbox 级工具过滤**

即使 agent 允许了 web 工具，sandbox 里还要允许对应工具组。

公开文档里把它拆成三层：

```text
agent-level tool allow/deny
sandbox-level tool filter
sandbox docker network
```

所以 web search 要能跑，不能只给 agent 开工具，还要 sandbox 放行 web 工具，并且容器网络不能是 `none`。

3. **Exec 安全策略**

OpenClaw 的 exec 有几个模式：

```text
deny       禁止所有 exec
allowlist 只允许白名单命令
full       全放开
```

这很像我们现在的：

```text
off / monitor / enforce
```

但 OpenClaw 更偏 shell exec 权限；myClaw 现在是所有工具统一 gate。

4. **Exec approval flow**

OpenClaw 对 shell 命令有 approval 机制。命令没命中 allowlist 时，会发 approval request，UI 或 macOS app 处理后再执行。

公开文档里说 approval 会绑定：

```text
canonical cwd
exact argv
env binding
pinned executable path
```

也就是说，它不只是问“你允许吗”，还会把当时批准的命令计划固定下来，防止批准后命令被偷偷改掉。

5. **系统事件**

OpenClaw 会把 exec 生命周期作为系统消息暴露：

```text
Exec running
Exec finished
Exec denied
```

这和 myClaw 的 `tool_gate_decision/tool_result` trace 目标类似，都是让用户看到工具执行生命周期。

6. **外部 harness hook relay**

OpenClaw 的 ACP 文档里还提到，针对 Codex-native 工具事件，会注入 hook relay，让插件可以：

```text
block before_tool_call
observe after_tool_call
route PermissionRequest through OpenClaw approvals
```

这就非常接近我们现在的设计：`before_tool_call` 能拦，`after_tool_call` 能观察，权限请求走 approval。

## 对 myClaw 的启发

现在 myClaw 已经有了第一版：

```text
before_tool_execute hook
ToolPolicy allow/ask/deny
前端确认
trace 记录
```

但和 OpenClaw 这类系统相比，还差几步：

1. **批准内容需要绑定得更细**

现在我们批准的是一次工具调用。后面应该绑定：

```text
tool_name
args hash
session_id
react_step
resource/action
```

防止“批准 A，执行 B”。

2. **需要 allowlist**

例如：

```text
本 session 允许 read_note
本项目允许 search_local_sources
永远不允许某些 shell pattern
```

3. **需要分层权限**

后面可以拆成：

```text
agent 可见工具
session 可用工具
resource/action 权限
tool 参数级权限
sandbox 硬边界
```

4. **需要 after_tool_call hook**

现在主要是 before。后面可以加：

```text
after_tool_call
```

用来检查：

```text
工具结果是否过长
是否泄露敏感路径
是否真的写入成功
是否需要更新 trace/eval 指标
```

这就是下一轮可以继续演进的方向。

这个设计参考的是 autosearch agent 常见策略：不是“默认永远联网”，也不是“默认永远不联网”，而是先判断信息缺口。

一个比较合理的搜索策略是：

```text
1. 用户问题是否需要外部世界的新信息？
2. 本地上下文、文件、trace、记忆是否已经足够回答？
3. 如果本地足够，不联网。
4. 如果需要新事实、新价格、新网页内容，再联网。
5. 如果不确定，就把原因写进 trace，必要时弹窗确认。
```

当前 myClaw 已经完成第一步本地检索接入。后续可以继续增强：

- 给每次回答记录 sources。
- 把本地检索结果和联网检索结果分开展示。
- 给 web_search 增加 query plan。
- 对“本地项目问题却联网”固化评测。

## 记忆写入保护

现在 `save_*` 和 `update_*` 已经有明确边界：

```text
save_note            只创建新笔记
update_note          只更新已有笔记
save_user_profile    只在 profile 不存在时创建
update_user_profile  更新已有 profile
write_office_file    只创建新文件
update_office_file   只更新已有文件
```

新增的保护包括：

- 空内容不允许写入 note/profile。
- `save_note` 会对正文做规范化 hash，重复内容不会再创建第二条 note。
- `update_note` 如果内容没变化，会返回 unchanged。
- `update_user_profile` 的 `merge` 模式不直接覆盖，而是追加带时间戳的 update。
- 如果 profile 里出现同名 key 的不同值，会写入 conflict notice，提醒后续 harness 做冲突处理。

这还不是最终记忆系统，但已经把“重复创建、空内容覆盖、长期画像被误清空”这些坏路径挡住了。

## 当前限制

现在 gate policy 已经能：

- 识别工具资源和动作。
- 记录风险。
- 记录 memory scope 判断。
- 记录 source routing 判断。
- 在 enforce 模式下弹窗等待用户确认。

但它还不是最终形态：

- 还没有持久化“总是允许这个工具”的授权。
- 还没有按 session / project / tool 参数做细粒度授权。
- memory scope 还是轻量规则，不是训练好的分类器。
- source routing 已接入轻量本地检索，但还没有 embedding、索引库和 source citation。
- 非流式调用没有前端等待确认弹窗，主要面向客户端流式会话。

下一步应该把这些判断继续固化成 eval，让每次 harness 改动都能看到：少写错长期记忆、少乱联网、少误写文件。

## 和 CyberClaw README 的差距

CyberClaw README 里提到的核心机制，myClaw 当前状态如下：

| CyberClaw 机制 | myClaw 当前状态 | 迁移建议 |
|---|---|---|
| 双水位记忆：长期画像 + 短期摘要 | 已有 profile 注入和 context trimming，但摘要较粗 | 下一步把摘要落盘，并区分“会话摘要”和“长期记忆候选” |
| 5 类事件审计 | 已有 llm_input/tool_call/tool_result/ai_message/tool_gate_decision/turn_completed | 继续统一 streaming 和 non-streaming 的 trace emitter |
| help → run 两段式技能 | 未实现 skill loader | 优先迁移 lazy skill loader，并固化两阶段 eval |
| 心跳任务引擎 | 只有 task CRUD，没有后台 heartbeat | 迁移 heartbeat loop，但先让任务 trace 可观测 |
| OpenClaw / Claude Code skill 兼容 | 未实现 | 先支持 SKILL.md 扫描和 help/run，再谈生态兼容 |
| Rich 监控终端 | 未实现，当前是 Mac 客户端 trace UI | 可以不迁移终端 UI，保留 Mac 客户端作为学习界面 |
| LangGraph checkpointer | myClaw 是自研 loop + JSON session | 学习阶段可继续自研，之后再对照 checkpointer 做持久化状态 |

## CyberClaw 的评测方式

CyberClaw 的测试主要分两类：

1. 单元/集成测试：

```text
python3 -m pytest tests/ -v
```

覆盖 agent 创建、内置工具、上下文裁剪、沙盒工具、心跳任务、skill loader。

2. 两阶段技能选择实验：

```text
python3 tests/test_two_phase_skills.py
```

这个实验会构造 20 个场景。每个场景都有一个“名字很像但会出事故的陷阱工具”和一个“真正正确的工具”。

它比较两种 agent：

- 单阶段：只看工具 brief，直接 run。
- 两阶段：先 `help` 看完整说明书，再决定是否 `run`。

README 里的结果是：

```text
安全命中率：50% -> 90%
P0 事故率：50% -> 10%
平均耗时：增加约 23.5%
```

这个评测很适合迁移到 myClaw，因为它直接对应 harness 价值：多一次受控观察，换来更少错误工具调用。

## myClaw 如何迁移 CyberClaw 评测

建议分三步：

1. 先把 `test_two_phase_skills.py` 改成 myClaw 版本。
   - 用 myClaw 的 `BaseTool` 创建一组 mock tools。
   - 每个工具支持 `mode=help/run`。
   - 记录 `tool_call`、`tool_result`、`tool_gate_decision`。

2. 把结果写成 eval trace。
   - 每个场景是一条 eval case。
   - 判定标准不是回答文字，而是工具轨迹：
     - 是否先 help。
     - 是否 run 了错误工具。
     - 是否在 help 后反悔。
     - 是否触发 gate。

3. 接到客户端评测 tab。
   - “启动评测”运行真实 agent。
   - 右侧展示每个场景的 ReAct steps。
   - 汇总 success/fatal/time。

迁移后，myClaw 的 eval 就不只是检查已有 JSON trace，而是真正启动新会话、跑工具选择实验、生成新轨迹。
