---
name: structured_memory_write
description: Use this skill when a task must create internal LightClaw notes, todos, or calendar events as observable artifacts.
---

# Structured Memory Write

## Tools

- `write_note`
- `add_todo`
- `add_calendar_event`

## Load Policy

Load this skill after the runtime has enough evidence to write a durable artifact.
For information extraction tasks, prefer retrieval/extraction first and write only after validation.

## Guardrails

- Do not persist speculative summaries.
- Required fields must be present before calling a write tool.
- If evidence is missing, ask for clarification or return a safe final answer instead of writing.
