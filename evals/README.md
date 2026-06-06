# myClaw Evals

This directory contains runnable regression evals for observed badcases.

## Current Eval

```bash
python -m evals.badcase_0001_context_memory
python -m evals.badcase_0001_context_memory --repeat 5
python -m evals.agent_eval_runner --suite basic_tasks
python -m evals.agent_eval_runner --suite basic_tasks --case calc_basic
python -m evals.agent_eval_runner --suite memory_policy_badcases
python -m evals.memory_policy_cases --suite memory_policy_badcases --case memory_case6
python -m evals.two_phase_skills
```

Each eval writes a JSONL run log under:

```text
runs/
```

## Agent-Level Eval

Agent-level evals start real interactive sessions and inspect the generated
trace. The first suite is:

```text
myClaw/evals/cases/basic_tasks.json
```

It covers README-style tasks: time query, calculator, scheduled task create/list,
office file listing, file creation, sandbox shell execution, and profile writes.

The suite defaults to `policy_mode=monitor`, so permission decisions are logged
without blocking basic capability checks. Dedicated policy evals should use
`enforce` mode to test ask/deny behavior.

The eval result itself is also a JSONL trace containing:

- `eval_suite_started`
- `eval_case_started`
- `eval_user_input`
- `eval_turn_replayed`
- `eval_case_completed`
- `eval_summary`

The Mac client can read these events directly in the Eval tab.

## Memory/Policy JSON Suite

Memory and policy badcases now live in:

```text
myClaw/evals/cases/memory_policy_badcases.json
```

This suite uses `runner: "trace_regression"` and points each case at one or
more historical JSONL traces. `agent_eval_runner` detects that runner type and
delegates to the memory/policy checker, so the client can launch it through the
same `start_agent_eval(suite)` command used by `basic_tasks`.

The generated eval log uses the same display events:

- `eval_suite_started`
- `eval_case_started`
- `eval_case_completed`
- `eval_summary`

## Interactive Testing

Use the CLI for exploratory testing:

```bash
python myClaw/main.py
```

The CLI prints the JSONL run log path at startup and still prints the human-readable TRACE after each turn.

## Observability Policy

The logger is intentionally small and append-only. As the harness evolves, add new event fields or new event names near the component being studied:

- context optimization: log trim decisions, kept turns, discarded turns, summary updates
- memory optimization: log profile reads/writes and memory capability flags
- tool optimization: log tool args, results, errors, retries, and permission checks
- concurrency optimization: log task ids, queue state, start/end timestamps
- eval optimization: log pass/fail criteria, judge output, and ablation labels

Keep evals focused on user-visible behavior, and use JSONL traces to explain why a behavior happened.

## CyberClaw Two-Phase Skill Eval

`two_phase_skills.py` ports the CyberClaw help/run experiment into myClaw's
eval surface. It uses deterministic queued model responses, so it can run
without an API key while still exercising the real myClaw harness and tool
execution path.

The eval asserts:

- both competing skill manuals were read with `mode="help"`
- the trap skill was never run
- the correct skill was run and returned success

This covers the main CyberClaw lesson: agent-level evals should inspect the
tool trajectory, not only the final answer.
