# Skill Management Design

## Goal

Improve LightClaw's skill management by borrowing the useful parts of Abu's skill model without copying Abu's full runtime.

The work will happen in two phases:

1. Enhance the existing lazy skill loader with Abu-style metadata.
2. Extract a small registry boundary so future agent profiles and MCP tools can reuse the same skill metadata model.

## Current Context

LightClaw already has:

- `core/skill_loader.py`, which scans `workspace/office/skills/*/SKILL.md` and exposes each skill as a lazy `FunctionTool`.
- A two-stage skill flow: `mode="help"` reads the manual, then `mode="run"` executes a command through the office shell sandbox.
- `core/policy.py`, which maps tool calls to permissions and gate decisions.
- A Tauri tool view that lists available tools through `list_agent_tools`.
- Tests for lazy loading, two-stage skill execution, policy gates, and tool listing behavior.

Abu's reference project adds useful skill metadata:

- `trigger`
- `do-not-trigger`
- `user-invocable`
- `disable-auto-invoke`
- `allowed-tools`
- `blocked-tools`
- `argument-hint`
- `tags`

LightClaw should parse and use these fields, but should keep its simpler local harness architecture.

## Phase 1: Loader Enhancement

Extend `LazySkillLoader` so it parses a fuller YAML-like frontmatter block from `SKILL.md` or `README.md`.

The parser should support the existing minimal files and Abu-style files. Missing fields should fall back to conservative defaults:

- `name`: folder name or frontmatter name.
- `description`: existing fallback description.
- `trigger`: empty string.
- `do_not_trigger`: empty string.
- `user_invocable`: true by default.
- `disable_auto_invoke`: false by default.
- `allowed_tools`: empty list means no extra restriction beyond the current sandbox.
- `blocked_tools`: empty list.
- `argument_hint`: empty string.
- `tags`: empty list.

The lazy tool description should include concise routing guidance:

- what the skill does,
- when it should trigger,
- when it should not trigger,
- whether it is user-invocable,
- and the first-use rule: call `mode="help"` before `mode="run"`.

The `mode="help"` result should include the full manual header plus the parsed metadata summary. The existing content truncation can remain, but the metadata should never be truncated away.

The `mode="run"` path should enforce first-version tool constraints:

- If `blocked-tools` includes `execute_office_shell` or wildcard patterns matching the run backend, reject the run.
- If `allowed-tools` is non-empty and does not include the run backend, reject the run.
- Keep execution inside the existing `execute_office_shell` sandbox.

This does not make arbitrary tools callable from inside a skill. It only prevents a skill from using the current shell-backed run path when its metadata says the shell is blocked or not allowed.

## Phase 2: Skill Registry Boundary

Introduce a lightweight `SkillManifest` data structure and a `SkillRegistry` helper. The registry should own scanning, metadata parsing, caching, and reload behavior. `LazySkillLoader` should become a thin adapter that converts manifests into `FunctionTool` instances.

The boundary should make these operations explicit:

- `list_manifests(force_rescan=False)`
- `get_manifest(name)`
- `reload()`
- `clear_cache()`
- `create_tool(manifest)`

This keeps current behavior intact while making future extensions easier:

- AGENT.md tool whitelists can choose skills by metadata.
- The UI can show skill metadata without reverse-engineering tool descriptions.
- MCP-discovered tools can later share the same manifest list shape.

## Data Flow

1. On startup, `ALL_TOOLS` still combines built-ins, file tools, shell tools, and dynamic skills.
2. Dynamic skills are still loaded lazily when `ALL_TOOLS` is iterated.
3. The registry scans `workspace/office/skills`.
4. Each skill folder produces one `SkillManifest`.
5. `LazySkillLoader` converts each manifest into one `FunctionTool`.
6. The agent sees richer descriptions and can choose skills more accurately.
7. The client can list parsed metadata through existing tool listing, with optional extra fields added by the Tauri command.

## Policy And Safety

This work should not weaken existing safety boundaries.

- `mode="run"` remains limited to `execute_office_shell`.
- The office shell sandbox remains the execution boundary.
- Existing policy gates still apply to the skill tool call itself.
- `allowed-tools` and `blocked-tools` are additional restrictions, not permissions grants.
- Unknown or malformed metadata should not crash scanning. It should degrade to defaults and include enough traceable information for tests.

## UI Impact

The initial UI change should be small:

- Tool cards can display `tags`, `user_invocable`, and routing hints when present.
- No new skill editor is required in this phase.
- No browser bridge, MCP manager, or custom agent UI is part of this scope.

If UI changes become noisy, they can be deferred. The backend metadata and tests are the required deliverable.

## Testing

Add focused tests for:

- Parsing Abu-style frontmatter fields.
- Preserving compatibility with old minimal `SKILL.md` files.
- Skill help output includes metadata summary.
- Skill run rejects blocked shell execution.
- Skill run rejects shell execution when `allowed-tools` excludes it.
- Reload still discovers newly added skills.

Existing tests for two-stage skill execution should continue to pass.

## Non-Goals

- Do not import Abu's full builtin skill library.
- Do not implement browser automation.
- Do not implement MCP client discovery yet.
- Do not implement AGENT.md profiles yet.
- Do not allow skills to execute arbitrary LightClaw tools from `allowed-tools`.

## Implementation Order

1. Add metadata parsing while keeping `LazySkillLoader` mostly intact.
2. Add tests for metadata parsing and run restrictions.
3. Update tool-list output to expose optional metadata.
4. Extract `SkillManifest` and `SkillRegistry` once phase 1 behavior is covered.
5. Update docs with the supported skill frontmatter format.

