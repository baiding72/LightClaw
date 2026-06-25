---
name: html-widget
description: Build small interactive HTML widgets for visual explanations, charts, demos, counters, simple games, algorithm animations, UI prototypes, and exploratory interactions.
trigger: user asks for an interactive demo, widget, animation, data chart, dashboard snippet, algorithm visualization, calculator, timer, mini tool, simple game, or UI prototype
do-not-trigger: user asks for a saved app file, production implementation in the repository, static infographic, Mermaid diagram, generated image, or pure text explanation
user-invocable: true
disable-auto-invoke: false
argument-hint: <widget behavior and content>
blocked-tools:
  - execute_office_shell
tags:
  - html
  - widget
  - interactive
  - abu-migrated
---

# HTML Widget

Generate an interactive HTML fragment in a fenced `html` code block.

## Output Format

Use this order:

```html
<style>
</style>

<div id="app"></div>

<script>
</script>
```

## Rules

- Do not write files unless the user explicitly asks for a repository/app implementation.
- Do not use external dependencies unless the user asks and the environment supports them.
- Keep the widget self-contained and responsive.
- Include empty, loading, and error states when relevant.
- Prefer clear controls: buttons, sliders, inputs, tabs, toggles, or selects.

## Visual Style

- Use a light, readable layout inside the widget.
- Avoid decorative clutter.
- Make the first view directly useful.
