---
name: browser_gui_control
description: Use this skill when a task requires visible browser interaction such as clicking, typing, selecting, scrolling, or taking screenshots.
---

# Browser GUI Control

## Tools

- `click`
- `type_text`
- `scroll`
- `select_option`
- `take_screenshot`

## Load Policy

Load this skill only when the selected target page must be manipulated or observed through GUI state.
For read-only static fixture extraction, prefer domain extractors instead of browser actions.

## Guardrails

- No target tab, no run.
- Do not submit forms unless a task is explicitly marked safe and the action is permitted.
- Stop on login, CAPTCHA, upload fields, or policy violations.
- Record GUI failures as recoverable observations, not silent retries.
