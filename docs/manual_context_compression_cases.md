# Context Compression Manual Test Cases

This document contains manual long-task cases for testing LightClaw context trimming and context guard behavior.

## Current Mechanism

The current implementation has two layers:

1. `AgentState.trim_context()` in `core/state.py`
   - Trigger: `len(state.messages) > 40`.
   - It only trims if there are more than 10 user messages.
   - It keeps messages starting from the 10th most recent user message.
   - Older user messages are truncated to 100 chars in `state.summary`.
   - Older assistant messages are truncated to 150 chars in `state.summary`.
   - Older tool messages are not included in the summary.
   - `state.tool_results` is reset after trimming.

2. `protect_state()` in `core/context_guard.py`
   - Estimates input tokens as `len(content) // 4`.
   - Compacts oversized tool messages above 4000 chars by keeping the head and tail.
   - If estimated input still exceeds 24000 tokens, it calls `state.trim_context()`.
   - Summary is capped at 2000 chars.

Important: some docs describe the trigger as "40 turns", but the current code uses total message count > 40. A ReAct loop with tool calls can hit trimming much earlier than 40 user turns.

## Case 1: Basic Multi-turn Compression

Purpose: verify trimming triggers after enough normal chat messages, keeps recent turns, and preserves older intent in summary.

Manual script:

```text
Turn 1: 记住本轮测试的项目代号是 CTX-ALPHA，只在当前会话使用，不要写入长期记忆。
Turn 2: 我们的目标是验证上下文压缩，不是测试回答质量。
Turn 3: 约束 A：所有最终回答都要用中文。
Turn 4: 约束 B：不要主动联网。
Turn 5: 约束 C：不要创建文件，除非我明确要求。
Turn 6: 标记 early-key-1 = "red-river"。
Turn 7: 标记 early-key-2 = "silver-bridge"。
Turn 8: 标记 early-key-3 = "north-star"。
Turn 9: 请只回复“收到 9”。
Turn 10: 请只回复“收到 10”。
Turn 11: 请只回复“收到 11”。
Turn 12: 请只回复“收到 12”。
Turn 13: 请只回复“收到 13”。
Turn 14: 请只回复“收到 14”。
Turn 15: 请只回复“收到 15”。
Turn 16: 请只回复“收到 16”。
Turn 17: 请只回复“收到 17”。
Turn 18: 请只回复“收到 18”。
Turn 19: 请只回复“收到 19”。
Turn 20: 请只回复“收到 20”。
Turn 21: 现在总结本轮测试的项目代号、目标、约束 A/B/C，以及 early-key-1/2/3。
```

Expected:

- After enough messages, `context_guard` or session trace should show trimming.
- Recent 10 user turns remain as raw messages.
- Older content should appear through `state.summary`.
- The final answer should still mention CTX-ALPHA and the three early keys.
- It should not claim those facts are long-term memory.

## Case 2: Tool-heavy ReAct Trims Earlier Than 40 User Turns

Purpose: verify that total message count, not user turn count, drives the basic threshold.

Manual script:

```text
Turn 1: 运行一个简单 shell 命令：printf 'tool-heavy-01'，然后告诉我输出。
Turn 2: 运行一个简单 shell 命令：printf 'tool-heavy-02'，然后告诉我输出。
Turn 3: 运行一个简单 shell 命令：printf 'tool-heavy-03'，然后告诉我输出。
Turn 4: 运行一个简单 shell 命令：printf 'tool-heavy-04'，然后告诉我输出。
Turn 5: 运行一个简单 shell 命令：printf 'tool-heavy-05'，然后告诉我输出。
Turn 6: 运行一个简单 shell 命令：printf 'tool-heavy-06'，然后告诉我输出。
Turn 7: 运行一个简单 shell 命令：printf 'tool-heavy-07'，然后告诉我输出。
Turn 8: 运行一个简单 shell 命令：printf 'tool-heavy-08'，然后告诉我输出。
Turn 9: 运行一个简单 shell 命令：printf 'tool-heavy-09'，然后告诉我输出。
Turn 10: 运行一个简单 shell 命令：printf 'tool-heavy-10'，然后告诉我输出。
Turn 11: 运行一个简单 shell 命令：printf 'tool-heavy-11'，然后告诉我输出。
Turn 12: 运行一个简单 shell 命令：printf 'tool-heavy-12'，然后告诉我输出。
Turn 13: 不要运行命令。告诉我第 1 轮和第 12 轮分别输出了什么。
```

Expected:

- Because each tool turn adds user, assistant, and tool messages, total messages should exceed 40 around 13 to 14 tool-heavy turns.
- Older tool messages are omitted from summary, so exact early tool output may only survive if it was repeated in assistant answers.
- This case exposes whether assistant final answers contain enough durable information before tool observations are trimmed.

## Case 3: Oversized Tool Result Compaction

Purpose: verify large tool results are head/tail compacted before history trimming.

Manual script:

```text
Turn 1: 运行命令生成一个很长的输出：python - <<'PY'
for i in range(1200):
    print(f"LONG_RESULT_LINE_{i:04d}")
PY
然后告诉我第一行、最后一行和总行数。

Turn 2: 不要重新运行命令。根据刚才的上下文，告诉我第一行、最后一行和总行数。
```

Expected:

- Trace should show `compacted_tool_results > 0`.
- Tool message content should contain a marker like `omitted ... chars from oversized tool result`.
- The assistant should preserve answer-critical facts in its own response.
- Turn 2 should not require rerunning the command.

## Case 4: Summary Must Not Preserve Full Tool Logs

Purpose: verify the known behavior that old tool messages are skipped in summary.

Manual script:

```text
Turn 1: 运行命令：printf 'SECRET_TOOL_ONLY_VALUE=delta-771\n'。回答时不要复述这个值，只说“命令已运行”。
Turn 2-20: 每轮只回复“继续 N”，其中 N 是当前轮数。
Turn 21: 不要重新运行任何命令。告诉我第 1 轮工具输出里的 SECRET_TOOL_ONLY_VALUE 是什么。
```

Expected:

- If trimming happened and the assistant never repeated the value, the value should not be recoverable from summary.
- The correct behavior is to say it cannot determine from current retained context, not hallucinate.
- This validates the tradeoff: tool observations are not durable unless promoted into assistant answer, note, or summary.

## Case 5: Temporary Session Constraint Survives Compression

Purpose: verify session-scoped instructions survive trimming without being written to long-term profile.

Manual script:

```text
Turn 1: 本轮测试临时约束：你最后回答必须以 “[CTX-TEMP-OK]” 结尾。这个约束只对当前会话有效，不要写入长期记忆。
Turn 2-22: 每轮只回答“推进 N”，其中 N 是当前轮数。
Turn 23: 现在回答一句话说明你是否还记得临时约束。
```

Expected:

- Final response should end with `[CTX-TEMP-OK]`.
- Trace or memory events should not show profile writes for this temporary constraint.
- If compression summary loses the constraint, this is a badcase for summary quality.

## Case 6: Recent Turn Fidelity After Trim

Purpose: verify recent 10 user turns are retained exactly, not just summarized.

Manual script:

```text
Turn 1-12: 每轮只回答“老轮次 N”。
Turn 13: recent-key-13 = apple-13
Turn 14: recent-key-14 = banana-14
Turn 15: recent-key-15 = cherry-15
Turn 16: recent-key-16 = durian-16
Turn 17: recent-key-17 = elderberry-17
Turn 18: recent-key-18 = fig-18
Turn 19: recent-key-19 = grape-19
Turn 20: recent-key-20 = honeydew-20
Turn 21: recent-key-21 = ita-palm-21
Turn 22: recent-key-22 = jackfruit-22
Turn 23: 列出 recent-key-13 到 recent-key-22 的完整值。
```

Expected:

- Keys from the most recent 10 user turns should be available with exact values.
- If one is missing, check whether an extra user turn shifted the retention window.

## Case 7: Compression During Multi-step File Task

Purpose: verify the agent can continue a long task after context guard events.

Manual script:

```text
Turn 1: 我要做一个手动测试计划。阶段 1 叫 collect，阶段 2 叫 mutate，阶段 3 叫 verify。最终不要提交 git。
Turn 2: 在当前仓库里找和 context guard 相关的文件，只汇报文件名。
Turn 3: 阅读 core/context_guard.py，只总结 protect_state 的触发条件。
Turn 4: 阅读 core/state.py，只总结 trim_context 的保留策略。
Turn 5: 阅读 tests/test_context_advanced.py，只总结现有覆盖。
Turn 6: 阅读 docs/interview_qa.md 的 Context Guard 部分，只总结文档说法。
Turn 7-18: 每轮让 agent 读取一个小文件并总结 1 句，例如 docs/tools.md、docs/session_management.md、docs/gate-policy.md 等。
Turn 19: 现在不要改代码。按 collect/mutate/verify 三阶段输出一个最终手测计划，并说明为什么不提交 git。
```

Expected:

- The agent should not forget "最终不要提交 git"。
- It should preserve the three phase names.
- It should not start editing files in the final turn.
- Trace should show whether large read outputs were compacted.

## Case 8: Conflicting Old And New Instructions

Purpose: verify recent turns override older summarized instructions after compression.

Manual script:

```text
Turn 1: 本轮输出格式暂定为 JSON。
Turn 2-18: 每轮只回复“padding N”。
Turn 19: 更新规则：从现在开始不要输出 JSON，改用三条中文 bullet。
Turn 20: 再次确认：不要 JSON。
Turn 21: 总结当前上下文压缩机制。
```

Expected:

- Final response should use three Chinese bullets, not JSON.
- The older summarized "JSON" instruction must not override newer raw turns.

## Case 9: Repeated Compression

Purpose: verify summary replacement behavior after multiple trims.

Manual script:

```text
Turn 1: 第一段早期事实：alpha-key = A-001。
Turn 2-22: 每轮只回复“第一批 padding N”。
Turn 23: 第二段中期事实：beta-key = B-002。
Turn 24-45: 每轮只回复“第二批 padding N”。
Turn 46: 现在列出 alpha-key 和 beta-key。
```

Expected:

- Current code replaces `state.summary` on each trim instead of recursively summarizing previous summary.
- This may lose `alpha-key` after repeated trims.
- If lost, classify as expected limitation or badcase depending on desired product behavior.

## Case 10: Resume Boundary

Purpose: verify session JSON and runtime summary boundary.

Manual script:

```text
Session A:
Turn 1: 本会话事实：resume-key = R-123。
Turn 2-22: 每轮只回复“resume padding N”。
Turn 23: 结束前告诉我 resume-key。

Restart or resume the same session if the product supports it.

Session B:
Turn 1: 不要查文件。告诉我 resume-key 是什么，以及它来自原始 transcript、summary 还是长期记忆。
```

Expected:

- If summary is not persisted in session metadata, resumed behavior depends on saved transcript and reconstruction logic.
- The assistant should not falsely claim the value came from long-term memory.
- If the value is unavailable after resume, the product needs persisted summary or transcript replay.
