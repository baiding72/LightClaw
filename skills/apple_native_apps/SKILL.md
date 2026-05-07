---
name: apple_native_apps
description: Use this skill when a task explicitly targets macOS Reminders or Notes through local native app integrations.
---

# Apple Native Apps

## Tools

- `create_apple_reminder`
- `list_apple_reminders`
- `create_apple_note`
- `list_apple_notes`
- `show_apple_reminder`
- `open_apple_note`

## Load Policy

Load this skill only when the task asks for native macOS app output or display.
For internal trajectory artifacts, use structured memory tools instead.

## Guardrails

- Do not store secrets or sensitive personal data.
- Prefer create/list calls over GUI automation for deterministic writes.
- Use show/open tools only when the user needs a visible demo or confirmation.
