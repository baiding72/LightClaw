---
name: doc-coauthoring
description: Guide users through a structured workflow for co-authoring documentation, proposals, technical specs, decision docs, RFCs, PRDs, and similar structured content.
trigger: user asks to write, draft, improve, or review a substantial document, proposal, spec, RFC, PRD, decision doc, or project write-up
do-not-trigger: user asks for a short one-off answer, simple copy edit, code implementation, or unrelated file operation
user-invocable: true
disable-auto-invoke: false
argument-hint: <document goal, audience, constraints, and any existing draft>
blocked-tools:
  - execute_office_shell
tags:
  - docs
  - writing
  - spec
  - abu-migrated
---

# Doc Co-Authoring Workflow

Use this skill to guide a user through collaborative document creation.

## Workflow

1. Context gathering
   - Identify document type, audience, desired reader impact, required template, deadline, and constraints.
   - Ask for existing notes, links, prior decisions, unresolved disagreements, and examples of preferred style.
   - If context is incomplete, ask focused questions before drafting.

2. Structure and drafting
   - Propose a concise outline first.
   - Draft section by section instead of producing a huge document at once.
   - Keep assumptions explicit and mark open questions.

3. Reader testing
   - Review the draft from the perspective of a reader with no prior context.
   - Check whether the problem, decision, evidence, alternatives, risks, and next steps are understandable.
   - Return concrete edits, missing context, and confusing sections.

## Output Style

- Keep the collaboration active: ask for missing information when it would materially change the document.
- Prefer headings, bullets, and decision tables over long prose.
- Do not invent organizational facts, stakeholder positions, metrics, or timelines.
