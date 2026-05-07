---
name: utility_reasoning
description: Use this skill for deterministic helper operations such as calculator-backed arithmetic.
---

# Utility Reasoning

## Tools

- `calculator`

## Load Policy

Load this skill only when a task requires deterministic calculation that should be logged as a tool call.

## Guardrails

- Keep calculation inputs explicit.
- Do not use calculator output as evidence for external facts.
