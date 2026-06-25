---
name: mermaid-diagram
description: Generate Mermaid diagrams for flowcharts, architecture diagrams, sequence diagrams, ER diagrams, state machines, Gantt charts, mind maps, timelines, and other structured technical diagrams.
trigger: user explicitly asks for Mermaid, ER diagram, sequence diagram, Gantt chart, state diagram, class diagram, mind map, git graph, or Mermaid syntax
do-not-trigger: user asks for a polished visual poster, interactive widget, photograph, illustration, logo, UI mockup, or generated image
user-invocable: true
disable-auto-invoke: false
argument-hint: <diagram description>
blocked-tools:
  - execute_office_shell
tags:
  - diagram
  - mermaid
  - visualization
  - abu-migrated
---

# Mermaid Diagram

Generate a single Mermaid diagram that matches the user's request.

## Rules

- Output a fenced `mermaid` code block as the primary answer.
- Use one diagram per code block.
- Prefer readable node labels in the user's language.
- Keep diagrams compact. If there are more than 20 nodes, group or simplify.
- Avoid characters that commonly break Mermaid labels unless escaped.

## Type Selection

- Process or decision: `flowchart TD` or `flowchart LR`.
- Message exchange: `sequenceDiagram`.
- Data model: `erDiagram`.
- State machine: `stateDiagram-v2`.
- Schedule: `gantt`.
- Branching history: `gitGraph`.
- Concept map: `mindmap`.

Add a short explanation only if it helps the reader interpret the diagram.
