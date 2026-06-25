---
name: skill-creator
description: Create, edit, optimize, and evaluate skills, including trigger boundaries, frontmatter metadata, examples, and test prompts.
trigger: user asks to create a new skill, modify an existing skill, improve skill trigger accuracy, migrate a skill, write skill tests, or evaluate whether a skill is appropriate
do-not-trigger: user only asks what skills are, discusses the concept generally, or mentions the word skill without asking to build or evaluate one
user-invocable: true
disable-auto-invoke: false
argument-hint: <skill goal, trigger cases, non-trigger cases, expected output, tools allowed>
blocked-tools:
  - execute_office_shell
tags:
  - skill
  - authoring
  - eval
  - abu-migrated
---

# Skill Creator

Use this skill to create or improve LightClaw skills.

## Skill Design Checklist

1. Intent
   - What task should the skill help with?
   - What output should it produce?
   - What tools, if any, should it be allowed to use?

2. Trigger boundary
   - Positive trigger examples.
   - Negative examples where the skill should not load.
   - Ambiguous cases and tie-breakers.

3. Frontmatter
   - `name`
   - `description`
   - `trigger`
   - `do-not-trigger`
   - `user-invocable`
   - `disable-auto-invoke`
   - `argument-hint`
   - `allowed-tools` or `blocked-tools`
   - `tags`

4. Body
   - Operational steps.
   - Output format.
   - Edge cases.
   - Safety and fallback rules.

5. Evaluation
   - At least 5 positive prompts.
   - At least 5 negative prompts.
   - Assertions for selected skill, avoided skill, tool calls, and final answer shape.

Prefer small, specific skills over broad skills that compete with many others.
