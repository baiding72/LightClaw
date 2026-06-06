# Badcase 0001: Current-Session Context Is Mistaken For No Memory

## Symptom

当前会话中存在历史消息，但模型仍声称自己没有上下文/记忆。

## Reproduction

In `python myClaw/main.py`, run a few interactions first, then ask:

```text
我刚刚在学习什么
```

Observed answer:

```text
抱歉，我没有记忆功能。每次对话都是独立的会话，我无法记住之前与你的交流内容。
```

Then ask:

```text
总结一下我们前面所有测试发现的问题
```

Observed answer may summarize previous tests from the same CLI session, proving that short-term `messages` context did exist.

## Root Cause

`myClaw/main.py` keeps current-session history in `conversation_state["messages"]`, but the default system prompt does not explicitly define the distinction between:

- current-session context available in `messages`
- summary memory reserved in state but not yet used
- long-term memory that does not exist yet

As a result, the model may fall back to a generic self-description like "I have no memory", even while the harness is passing previous messages.

## Impact

用户会误以为系统没有上下文，agent 行为不稳定。

This also weakens evaluation because the same session can produce contradictory claims:

- one answer denies access to prior context
- another answer uses prior context successfully

## Candidate Fixes

Prompt-only fix:

- Teach the model to distinguish current-session context from long-term memory.
- Tell it not to broadly say "I have no memory" when current-session `messages` are available.

Harness-level fixes:

- Add a compact, structured context manifest before each LLM call.
- Track session metadata such as turn count, recent user topics, and whether long-term memory is enabled.
- Add a deterministic pre-answer guard for context/meta-memory questions.
- Add regression evals for "刚刚/前面/我们刚才" queries.

## Regression Test Idea

Interaction:

```text
User: 我们正在学习 myClaw MVP
User: 我刚刚在学习什么？
Expected: 你刚刚在学习 myClaw MVP
```

The expected answer should use current-session context without claiming cross-session long-term memory.

## Automated Eval

Run from the repo root:

```bash
python -m myClaw.evals.badcase_0001_context_memory
```

Pass criteria:

- The answer mentions both `myClaw` and `MVP`.
- The answer does not claim broad memory denial such as "没有记忆", "无法记住", or "每次对话都是独立".
