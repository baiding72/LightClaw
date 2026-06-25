---
name: internal-comms
description: Draft internal communications such as status reports, leadership updates, 3P updates, project updates, FAQs, incident updates, and company announcements.
trigger: user asks to write or improve an internal update, status report, leadership note, FAQ, incident report, newsletter, project update, or 3P update
do-not-trigger: user asks for external marketing copy, legal notices, public press releases, or unrelated technical implementation
user-invocable: true
disable-auto-invoke: false
argument-hint: <communication type, audience, facts, tone, deadline>
blocked-tools:
  - execute_office_shell
tags:
  - writing
  - comms
  - status
  - abu-migrated
---

# Internal Communications

Use this skill when drafting clear internal communication.

## Process

1. Identify the format:
   - 3P update: progress, plans, problems.
   - Leadership update: decision context, impact, risks, asks.
   - FAQ: crisp questions and direct answers.
   - Incident update: impact, current status, timeline, mitigation, owner.
   - General update: context, what changed, what it means, next steps.

2. Gather facts:
   - Audience and their current knowledge.
   - Exact status, dates, numbers, owners, and blockers.
   - Desired action after reading.

3. Draft:
   - Put the most important takeaway first.
   - Separate facts from interpretation.
   - Include an explicit ask when action is needed.

## Style

- Direct, calm, and concrete.
- Avoid vague progress words without evidence.
- Do not fabricate metrics, dates, owners, or commitments.
