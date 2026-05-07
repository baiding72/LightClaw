---
name: information_retrieval
description: Use this skill when a task needs to read existing local artifacts such as files, notes, todos, or calendar-like records before deciding what to do next.
---

# Information Retrieval

## Tools

- `read_file`
- `read_notes`
- `list_todos`
- `list_calendar_events`

## Load Policy

Load this skill only when the current task requires existing state or local context.
Do not load write or browser tools unless the plan requires mutation or GUI action.

## Guardrails

- Treat retrieved content as observation, not final evidence unless the task asks for local data.
- Do not infer missing facts from absent files or empty records.
