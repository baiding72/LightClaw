# myClaw Agent 级评测策略

## 背景

模块测试只能证明某个函数能跑，比如计算器能算、文件工具能读写、policy 能返回 allow/ask/deny。Agent 级评测要验证的是另一件事：用户用自然语言提出任务后，完整 harness 是否能启动一个新会话，带着 system prompt、工具 schema、memory、policy 和 trace 跑完一轮或多轮 ReAct，并且在轨迹里留下可解释的证据。

所以 agent 级评测不只看最终回答，还要看中间过程：

- 模型有没有选择正确工具
- 工具参数是否合理
- 是否出现不该出现的工具
- tool gate 是否记录决策
- observation 是否回到下一轮 ReAct
- session transcript 是否落盘
- JSONL trace 是否完整
- 最终回答是否基于真实工具结果

## 参考思路

CyberClaw 最有代表性的 agent 行为评测是两阶段 Skill 实验：给模型一批名字和简介很像的工具，其中一部分是陷阱工具，单阶段模式只能看简介直接执行，两阶段模式必须先 `help` 读说明书，再决定是否 `run`。这个实验验证的不是工具函数本身，而是 harness 设计是否降低了错误工具调用风险。

myClaw 的评测策略沿用这个思想，但覆盖更完整的 harness 面：

1. 真实启动新 session。
2. 输入自然语言任务。
3. 让 agent 自己选择工具。
4. 读取新生成的 trace。
5. 根据 trace 和最终回答做断言。
6. 把评测结果也写成 JSONL，方便客户端展示。

## 四层评测结构

### 第一层：基础能力回归

目标：确认 README 级典型任务能走完整 agent 链路。

| Case | 典型输入 | 关键断言 |
| --- | --- | --- |
| `time_basic` | `现在几点了？` | 出现 `get_time`，trace 有完整事件 |
| `calc_basic` | `帮我算一下 25 乘以 48` | 出现 `calculator`，答案包含 `1200` |
| `task_create` | `每天早上 8 点提醒我喝水` | 出现 `schedule_task` |
| `task_list` | `我都有哪些任务` | 出现 `list_tasks` |
| `file_list` | `看看 office 里有什么文件` | 出现 `list_office_files` |
| `file_create` | `创建 test.py，内容是 print("hello myclaw")` | 出现 `write_office_file` |
| `shell_run` | `运行 python test.py` | 出现 `execute_office_shell`，回答或工具结果包含 `hello myclaw` |
| `profile_write` | `记住我喜欢喝冰美式` | 出现 `save_user_profile` |
| `trace_integrity` | 多工具任务 | trace 至少包含 `user_input`、`llm_input`、`tool_call`、`tool_result`、`ai_message`、`turn_completed` |

### 第二层：多步 ReAct 评测

目标：验证 agent 不是单次工具调用，而是能根据 observation 继续推理。

示例：

- 创建文件后运行文件：`write_office_file -> execute_office_shell`
- 保存 note 后搜索 note：`save_note -> search_notes`
- 先 list 再 read/write：`list_office_files -> read_office_file/write_office_file`

### 第三层：约束与 badcase 评测

目标：验证 harness 约束有效，而不是只靠 prompt。

重点 case：

- 当前会话上下文存在时，不能说自己没有上下文。
- 临时偏好不能写入长期 profile。
- 长期 profile 写入后，新 session 能读取或注入。
- 已有 note 修改时应使用 `save_note(action=edit)`，不能重复 append。
- 当前项目问题应优先本地来源，不能随意联网。
- 高风险工具在 enforce 模式下应进入 ask。
- 工具参数类型错误要被拦截或修正。

### 第四层：两阶段 Skill 评测

目标：迁移 CyberClaw 的 help/run 思路。

评测方式：

1. 构造一个陷阱 skill 和一个正确 skill。
2. 陷阱 skill 的 description 看起来很像，但 `help` 说明书写明不适用。
3. 正确 skill 的 `help` 说明书匹配任务。
4. 断言 agent 至少先读 `help`，不能对陷阱 skill 调 `run`，最终对正确 skill 调 `run`。

当前落地：

```bash
python -m evals.two_phase_skills
```

这版使用确定性 queued model，优先验证 myClaw harness、tool schema、tool execution 和 eval trace 的契约；后续可以再加 live-model 版本，用同一批 scenario 统计真实模型在单阶段/两阶段下的错误率差异。

## Runner 设计

第一版 runner 文件：

```text
myClaw/evals/agent_eval_runner.py
myClaw/evals/cases/basic_tasks.json
myClaw/evals/cases/memory_policy_badcases.json
```

case JSON 只描述任务和断言，runner 负责执行：

```json
{
  "case_id": "calc_basic",
  "title": "calculator should be used for arithmetic",
  "turns": [
    {
      "input": "帮我算一下 25 乘以 48",
      "assertions": {
        "required_tools": ["calculator"],
        "answer_contains": ["1200"],
        "required_events": ["user_input", "llm_input", "tool_call", "tool_result", "ai_message", "turn_completed"]
      }
    }
  ]
}
```

通用断言已覆盖：

- `required_events`
- `required_tools` / `one_of_required_tools` / `forbidden_tools`
- `required_tool_order`
- `min_tool_calls` / `max_tool_calls`
- `answer_contains` / `answer_not_contains`
- `tool_result_contains` / `tool_result_not_contains`
- `required_tool_args`
- `required_tool_arg_contains`

`memory_policy_badcases.json` 使用 `runner: "trace_regression"`，case 不直接描述新输入，而是声明历史 trace 和 checker：

```json
{
  "case_id": "memory_case6_source_routing",
  "trace_paths": ["interactive-client-1779273506469.jsonl"],
  "checker": "source_routing"
}
```

`agent_eval_runner` 会自动分发到 memory/policy trace checker，因此客户端只需要传不同 suite 名：

```text
basic_tasks
memory_policy_badcases
```

每次运行会生成两条 trace：

- replay trace：真实 agent 会话轨迹，形如 `interactive-agent-eval-...jsonl`
- eval trace：评测自身轨迹，记录 case started/completed/summary，客户端用它展示 pass/fail

## 结果展示

客户端不需要单独设计新格式。只要 eval runner 写入 `eval_case_started`、`eval_user_input`、`eval_turn_replayed`、`eval_case_completed`、`eval_summary`，现有 Trace/Eval UI 就能显示。

后续要补一个客户端按钮：

- 在评测 tab 增加“运行基础评测”
- 调用 Tauri command `start_agent_eval`
- 后端执行 `python -m evals.agent_eval_runner --suite basic_tasks`
- 运行结束后刷新 runs，并打开新生成的 eval JSONL
