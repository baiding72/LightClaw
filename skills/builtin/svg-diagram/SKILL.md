---
name: svg-diagram
description: Generate clean SVG diagrams for architecture, process, hierarchy, comparison, roadmap, relationship, and system diagrams when a more polished layout than Mermaid is useful.
trigger: user asks to draw an architecture diagram, flow diagram, hierarchy, roadmap, comparison chart, topology, system diagram, data flow, or structured visual diagram
do-not-trigger: user explicitly asks for Mermaid syntax, generated images, photos, logos, interactive widgets, dashboards, or data analysis
user-invocable: true
disable-auto-invoke: false
argument-hint: <diagram description>
blocked-tools:
  - execute_office_shell
tags:
  - diagram
  - svg
  - visualization
  - abu-migrated
---

# SVG Diagram

Generate a clean SVG diagram inside a fenced `html` code block.

## Rules

- Return an HTML fragment containing `<style>` and `<svg>`.
- Do not use scripts, external assets, or generated images.
- Use a 720px viewBox width and enough height for the content.
- Keep labels readable. Minimum font size is 11px.
- Use simple fills, strokes, and arrows. Avoid heavy shadows and decorative gradients.

## Layout

- Use top-down layout for layered systems.
- Use left-to-right layout for flows and sequences.
- Group related nodes with subtle containers.
- Keep at least 20px spacing between nodes.

If the user asks for something better handled by Mermaid, use `mermaid-diagram` instead.
