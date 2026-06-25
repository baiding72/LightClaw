# Skill Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Abu-style skill metadata support to LightClaw, then extract a small registry boundary for future agent and MCP integrations.

**Architecture:** Phase 1 extends the existing `LazySkillLoader` behavior in place and protects it with tests. Phase 2 introduces `SkillManifest` and `SkillRegistry`, then makes `LazySkillLoader` a thin adapter from manifests to `FunctionTool` instances.

**Tech Stack:** Python 3.11+, pytest, existing LightClaw `FunctionTool` abstraction, Tauri Rust command that executes Python for tool listing, React/TypeScript tool cards.

## Global Constraints

- Keep `mode="run"` limited to the existing `execute_office_shell` sandbox.
- Treat `allowed-tools` and `blocked-tools` as additional restrictions, not permission grants.
- Missing or malformed metadata must not crash skill scanning.
- Preserve compatibility with existing minimal `SKILL.md` files.
- Do not implement browser automation, MCP client discovery, or AGENT.md profiles in this work.

---

### Task 1: Parse Abu-Style Skill Metadata In Place

**Files:**
- Modify: `core/skill_loader.py`
- Test: `tests/test_skill_loader.py`

**Interfaces:**
- Consumes: `LazySkillLoader.load_dynamic_skills(force_rescan=True)`.
- Produces: dynamic skill tools with a `skill_metadata: dict[str, Any]` attribute and metadata-aware descriptions.

- [ ] **Step 1: Write failing metadata parsing tests**

Add this test to `tests/test_skill_loader.py`:

```python
def test_lazy_skill_loader_parses_abu_style_metadata(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "office" / "skills"
    skill_dir = skills_dir / "browserish"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: browserish
description: Operate a browser-like target.
trigger: user asks to click or extract page data
do-not-trigger: user asks for local unit tests
user-invocable: false
disable-auto-invoke: true
argument-hint: <browser task>
allowed-tools:
  - execute_office_shell
blocked-tools:
  - dangerous_tool
tags:
  - browser
  - automation
---

# Browserish

Manual body.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)
    skill_loader.clear_skill_cache()

    [tool] = skill_loader.load_dynamic_skills(force_rescan=True)

    assert tool.name == "browserish"
    assert "Operate a browser-like target." in tool.description
    assert "Trigger: user asks to click or extract page data" in tool.description
    assert "Do not trigger: user asks for local unit tests" in tool.description
    assert tool.skill_metadata["trigger"] == "user asks to click or extract page data"
    assert tool.skill_metadata["do_not_trigger"] == "user asks for local unit tests"
    assert tool.skill_metadata["user_invocable"] is False
    assert tool.skill_metadata["disable_auto_invoke"] is True
    assert tool.skill_metadata["argument_hint"] == "<browser task>"
    assert tool.skill_metadata["allowed_tools"] == ["execute_office_shell"]
    assert tool.skill_metadata["blocked_tools"] == ["dangerous_tool"]
    assert tool.skill_metadata["tags"] == ["browser", "automation"]
```

Also add this compatibility test:

```python
def test_lazy_skill_loader_metadata_defaults_for_minimal_skill(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "office" / "skills"
    _write_skill(skills_dir, folder="plain", name="plain")
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)
    skill_loader.clear_skill_cache()

    [tool] = skill_loader.load_dynamic_skills(force_rescan=True)

    assert tool.skill_metadata["trigger"] == ""
    assert tool.skill_metadata["do_not_trigger"] == ""
    assert tool.skill_metadata["user_invocable"] is True
    assert tool.skill_metadata["disable_auto_invoke"] is False
    assert tool.skill_metadata["allowed_tools"] == []
    assert tool.skill_metadata["blocked_tools"] == []
    assert tool.skill_metadata["argument_hint"] == ""
    assert tool.skill_metadata["tags"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_skill_loader.py::test_lazy_skill_loader_parses_abu_style_metadata tests/test_skill_loader.py::test_lazy_skill_loader_metadata_defaults_for_minimal_skill -q`

Expected: FAIL because `FunctionTool` objects do not yet have `skill_metadata`, and the old parser ignores Abu fields.

- [ ] **Step 3: Implement metadata parsing**

In `core/skill_loader.py`, add helpers near `LazySkillLoader`:

```python
def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]
```

Replace `_extract_metadata` with a parser that reads the first frontmatter block and supports simple list values:

```python
def _extract_metadata(self, md_path: Path) -> dict[str, Any] | None:
    try:
        lines = md_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None

    fields: dict[str, Any] = {}
    if lines and lines[0].strip() == "---":
        current_key: str | None = None
        current_items: list[str] = []
        for raw in lines[1:]:
            if raw.strip() == "---":
                if current_key:
                    fields[current_key] = current_items
                break
            if raw.startswith("  - ") and current_key:
                current_items.append(raw[4:].strip().strip("\"'"))
                continue
            if ":" not in raw:
                continue
            if current_key:
                fields[current_key] = current_items
                current_key = None
                current_items = []
            key, value = raw.split(":", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if value:
                fields[key] = value
            else:
                current_key = key
                current_items = []
    else:
        content = "\n".join(lines[:50])
        for key in ("name", "description"):
            match = re.search(rf"^{key}:\s*(.+)$", content, re.MULTILINE)
            if match:
                fields[key] = match.group(1).strip().strip("\"'")

    raw_name = str(fields.get("name") or md_path.parent.name).strip("\"'")
    tool_name = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name).strip("_") or md_path.parent.name
    raw_desc = str(fields.get("description") or f"Provides {raw_name} skill functions.").strip("\"'")
    return {
        "raw_name": raw_name,
        "name": tool_name,
        "description": raw_desc,
        "trigger": str(fields.get("trigger") or ""),
        "do_not_trigger": str(fields.get("do-not-trigger") or fields.get("do_not_trigger") or ""),
        "user_invocable": _parse_bool(fields.get("user-invocable", fields.get("user_invocable")), True),
        "disable_auto_invoke": _parse_bool(fields.get("disable-auto-invoke", fields.get("disable_auto_invoke")), False),
        "allowed_tools": _parse_list(fields.get("allowed-tools", fields.get("allowed_tools"))),
        "blocked_tools": _parse_list(fields.get("blocked-tools", fields.get("blocked_tools"))),
        "argument_hint": str(fields.get("argument-hint") or fields.get("argument_hint") or ""),
        "tags": _parse_list(fields.get("tags")),
    }
```

Update `_create_lazy_tool` so the returned `FunctionTool` gets `skill_metadata`:

```python
tool = FunctionTool(
    lazy_runner,
    name=str(skill_info["name"]),
    description=description,
    parameters=parameters,
)
tool.skill_metadata = {
    key: skill_info[key]
    for key in [
        "raw_name",
        "trigger",
        "do_not_trigger",
        "user_invocable",
        "disable_auto_invoke",
        "allowed_tools",
        "blocked_tools",
        "argument_hint",
        "tags",
    ]
}
return tool
```

Build `description` from non-empty metadata fields before the existing first-call instruction:

```python
description_parts = [str(skill_info["description"])]
if skill_info.get("trigger"):
    description_parts.append(f"Trigger: {skill_info['trigger']}")
if skill_info.get("do_not_trigger"):
    description_parts.append(f"Do not trigger: {skill_info['do_not_trigger']}")
description_parts.append(f"User-invocable: {bool(skill_info.get('user_invocable', True))}")
description_parts.append(
    "External skill. First call mode='help' to read the full SKILL.md manual; "
    "then call mode='run' with command only if the manual fits the task."
)
description = "\n\n".join(description_parts)
```

- [ ] **Step 4: Run metadata parsing tests**

Run: `python3 -m pytest tests/test_skill_loader.py::test_lazy_skill_loader_parses_abu_style_metadata tests/test_skill_loader.py::test_lazy_skill_loader_metadata_defaults_for_minimal_skill -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add core/skill_loader.py tests/test_skill_loader.py
git commit -m "feat: parse skill metadata"
```

### Task 2: Add Help Output Metadata And Run Restrictions

**Files:**
- Modify: `core/skill_loader.py`
- Test: `tests/test_skill_loader.py`

**Interfaces:**
- Consumes: `tool.skill_metadata` from Task 1.
- Produces: help output with a metadata summary and run rejection based on `allowed_tools` / `blocked_tools`.

- [ ] **Step 1: Write failing tests for help and run restrictions**

Add these tests to `tests/test_skill_loader.py`:

```python
def test_lazy_skill_help_includes_metadata_summary(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "office" / "skills"
    skill_dir = skills_dir / "reporting"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: reporting
description: Builds reports.
trigger: user asks for reports
tags:
  - docs
---

# Reporting

Manual body.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)
    skill_loader.clear_skill_cache()
    [tool] = skill_loader.load_dynamic_skills(force_rescan=True)

    result = tool.invoke({"mode": "help"})

    assert "Metadata:" in result
    assert "trigger: user asks for reports" in result
    assert "tags: docs" in result
    assert "# Reporting" in result
```

```python
def test_lazy_skill_run_rejects_blocked_shell_backend(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "office" / "skills"
    skill_dir = skills_dir / "no_shell"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: no_shell
description: Does not allow shell.
blocked-tools:
  - execute_office_shell
---

# No Shell
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)
    skill_loader.clear_skill_cache()
    [tool] = skill_loader.load_dynamic_skills(force_rescan=True)

    result = tool.invoke({"mode": "run", "command": "echo should-not-run"})

    assert "Error:" in result
    assert "blocked-tools" in result
    assert "execute_office_shell" in result
```

```python
def test_lazy_skill_run_rejects_when_allowed_tools_excludes_shell(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "office" / "skills"
    skill_dir = skills_dir / "read_only"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: read_only
description: Only allows reads.
allowed-tools:
  - read_office_file
---

# Read Only
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)
    skill_loader.clear_skill_cache()
    [tool] = skill_loader.load_dynamic_skills(force_rescan=True)

    result = tool.invoke({"mode": "run", "command": "echo should-not-run"})

    assert "Error:" in result
    assert "allowed-tools" in result
    assert "execute_office_shell" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_skill_loader.py::test_lazy_skill_help_includes_metadata_summary tests/test_skill_loader.py::test_lazy_skill_run_rejects_blocked_shell_backend tests/test_skill_loader.py::test_lazy_skill_run_rejects_when_allowed_tools_excludes_shell -q`

Expected: FAIL because help output has no metadata block and run constraints are not enforced.

- [ ] **Step 3: Implement metadata summary and restriction checks**

In `core/skill_loader.py`, add:

```python
def _matches_tool_pattern(patterns: list[str], tool_name: str) -> bool:
    return any(fnmatch.fnmatch(tool_name, pattern) for pattern in patterns)


def _format_metadata_summary(skill_info: dict[str, Any]) -> str:
    rows = []
    for key in ["trigger", "do_not_trigger", "argument_hint"]:
        value = skill_info.get(key)
        if value:
            rows.append(f"- {key}: {value}")
    for key in ["allowed_tools", "blocked_tools", "tags"]:
        value = skill_info.get(key) or []
        if value:
            rows.append(f"- {key}: {', '.join(value)}")
    rows.append(f"- user_invocable: {bool(skill_info.get('user_invocable', True))}")
    rows.append(f"- disable_auto_invoke: {bool(skill_info.get('disable_auto_invoke', False))}")
    return "Metadata:\n" + "\n".join(rows)
```

Add `import fnmatch` at the top.

Inside `lazy_runner`, before running `execute_office_shell`, check:

```python
run_backend = "execute_office_shell"
blocked_tools = list(skill_info.get("blocked_tools") or [])
allowed_tools = list(skill_info.get("allowed_tools") or [])
if _matches_tool_pattern(blocked_tools, run_backend):
    return f"Error: this skill blocks {run_backend} via blocked-tools."
if allowed_tools and not _matches_tool_pattern(allowed_tools, run_backend):
    return f"Error: this skill allowed-tools does not include {run_backend}."
```

In the help branch, include the summary before manual content:

```python
metadata_summary = _format_metadata_summary(skill_info)
return (
    f"========== [{skill_info['raw_name']} manual] ==========\n"
    f"{metadata_summary}\n\n"
    f"{skill_content[:3000]}\n"
    f"====================================\n"
    "If this skill fits the task, call this same tool again with mode='run' "
    "and a concrete non-interactive command. Use {baseDir} for the skill directory."
)
```

- [ ] **Step 4: Run focused tests**

Run: `python3 -m pytest tests/test_skill_loader.py::test_lazy_skill_help_includes_metadata_summary tests/test_skill_loader.py::test_lazy_skill_run_rejects_blocked_shell_backend tests/test_skill_loader.py::test_lazy_skill_run_rejects_when_allowed_tools_excludes_shell -q`

Expected: PASS.

- [ ] **Step 5: Run full skill loader tests**

Run: `python3 -m pytest tests/test_skill_loader.py tests/test_config_and_skill_loader.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add core/skill_loader.py tests/test_skill_loader.py
git commit -m "feat: enforce skill tool restrictions"
```

### Task 3: Expose Skill Metadata In Tool Listing

**Files:**
- Modify: `client/src-tauri/src/main.rs`
- Modify: `client/src/main.tsx`

**Interfaces:**
- Consumes: optional Python `tool.skill_metadata` attributes.
- Produces: `list_agent_tools` JSON containing `skill_metadata`, and React tool cards displaying tags/routing hints when present.

- [ ] **Step 1: Update Rust command Python script**

In `client/src-tauri/src/main.rs`, inside the Python script in `list_agent_tools`, add:

```python
metadata = getattr(tool, "skill_metadata", None)
item = {
    "name": schema.get("name", ""),
    "description": schema.get("description", ""),
    "parameters": params.get("properties", {}),
    "required": params.get("required", []),
    "permission": permission.key,
    "resource": permission.resource,
    "action": permission.action,
    "risk": permission.risk,
    "requires_consent": permission.requires_consent,
}
if metadata:
    item["skill_metadata"] = metadata
items.append(item)
```

Replace the current direct `items.append({...})` block with this code.

- [ ] **Step 2: Update TypeScript types**

In `client/src/main.tsx`, extend the `ToolSummary` type with:

```ts
  skill_metadata?: {
    raw_name?: string;
    trigger?: string;
    do_not_trigger?: string;
    user_invocable?: boolean;
    disable_auto_invoke?: boolean;
    allowed_tools?: string[];
    blocked_tools?: string[];
    argument_hint?: string;
    tags?: string[];
  };
```

- [ ] **Step 3: Render compact skill metadata**

In the tool card body, after the permission row and before `param-list`, add:

```tsx
                    {tool.skill_metadata ? (
                      <div className="tool-meta-row">
                        <span>{tool.skill_metadata.user_invocable === false ? "not user-invocable" : "user-invocable"}</span>
                        <span>{tool.skill_metadata.tags?.length ? tool.skill_metadata.tags.join(", ") : "skill"}</span>
                      </div>
                    ) : null}
```

Keep this compact. Do not add new CSS unless the existing `.tool-meta-row` spacing breaks.

- [ ] **Step 4: Verify frontend typecheck/build**

Run: `cd client && npm run build`

Expected: PASS TypeScript and Vite build. If the build also triggers Tauri compilation and fails for unrelated local environment reasons, capture the exact failure and run `cd client && npx tsc --noEmit` as the minimum frontend verification.

- [ ] **Step 5: Commit**

Run:

```bash
git add client/src-tauri/src/main.rs client/src/main.tsx
git commit -m "feat: show skill metadata in tools"
```

### Task 4: Extract SkillManifest And SkillRegistry

**Files:**
- Modify: `core/skill_loader.py`
- Test: `tests/test_skill_loader.py`

**Interfaces:**
- Consumes: Task 1 and Task 2 behavior.
- Produces: `SkillManifest`, `SkillRegistry`, and existing public functions still working: `load_dynamic_skills`, `reload_skills`, `get_skill_count`, `clear_skill_cache`.

- [ ] **Step 1: Write registry tests**

Add this test to `tests/test_skill_loader.py`:

```python
def test_skill_registry_lists_manifests_and_gets_by_name(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "office" / "skills"
    _write_skill(skills_dir, folder="one", name="one")
    _write_skill(skills_dir, folder="two", name="two")
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)

    registry = skill_loader.SkillRegistry(skills_dir=skills_dir)

    manifests = registry.list_manifests(force_rescan=True)

    assert [manifest.name for manifest in manifests] == ["one", "two"]
    assert registry.get_manifest("one").raw_name == "one"
    assert registry.get_manifest("missing") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_skill_loader.py::test_skill_registry_lists_manifests_and_gets_by_name -q`

Expected: FAIL because `SkillRegistry` does not exist.

- [ ] **Step 3: Add manifest dataclass and registry**

In `core/skill_loader.py`, add:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SkillManifest:
    folder: str
    md_path: str
    mtime: float
    raw_name: str
    name: str
    description: str
    trigger: str = ""
    do_not_trigger: str = ""
    user_invocable: bool = True
    disable_auto_invoke: bool = False
    allowed_tools: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)
    argument_hint: str = ""
    tags: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "raw_name": self.raw_name,
            "trigger": self.trigger,
            "do_not_trigger": self.do_not_trigger,
            "user_invocable": self.user_invocable,
            "disable_auto_invoke": self.disable_auto_invoke,
            "allowed_tools": list(self.allowed_tools),
            "blocked_tools": list(self.blocked_tools),
            "argument_hint": self.argument_hint,
            "tags": list(self.tags),
        }
```

Add `SkillRegistry` with `list_manifests`, `get_manifest`, `reload`, and `clear_cache`. Move the scan and metadata extraction logic from `LazySkillLoader` into it. Its constructor should accept `skills_dir: Path | None = None` and default to `SKILLS_DIR`.

- [ ] **Step 4: Make LazySkillLoader use SkillRegistry**

Update `LazySkillLoader.__init__`:

```python
def __init__(self, cache_size: int = 50, scan_interval: int = 60, registry: SkillRegistry | None = None) -> None:
    self.registry = registry or SkillRegistry(scan_interval=scan_interval)
```

Change `get_all_tools`:

```python
def get_all_tools(self, force_rescan: bool = False) -> list[FunctionTool]:
    return [self._create_lazy_tool(manifest) for manifest in self.registry.list_manifests(force_rescan=force_rescan)]
```

Change `get_tool_count` and `clear_cache` to delegate to the registry and clear the content cache.

Update `_create_lazy_tool` to accept `manifest: SkillManifest` and use `manifest.metadata()` plus attributes instead of dict indexing.

- [ ] **Step 5: Run registry and existing skill tests**

Run: `python3 -m pytest tests/test_skill_loader.py tests/test_config_and_skill_loader.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add core/skill_loader.py tests/test_skill_loader.py
git commit -m "refactor: add skill registry"
```

### Task 5: Document Supported Skill Frontmatter

**Files:**
- Modify: `docs/tools.md`
- Test: none required; documentation only.

**Interfaces:**
- Consumes: final supported frontmatter fields from Tasks 1-4.
- Produces: project documentation showing the LightClaw skill metadata format.

- [ ] **Step 1: Add docs section**

Append this section to `docs/tools.md`:

```markdown
## Skill Frontmatter Metadata

Dynamic skills live under `workspace/office/skills/<skill-name>/SKILL.md`.
LightClaw reads the frontmatter block, exposes the skill as one lazy tool, and loads the manual only when the model calls the skill with `mode="help"`.

Supported fields:

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | string | folder name | Tool-safe skill name. |
| `description` | string | generated fallback | Short summary shown in the tool list. |
| `trigger` | string | empty | When the agent should consider this skill. |
| `do-not-trigger` | string | empty | When the agent should avoid this skill. |
| `user-invocable` | boolean | `true` | Whether users can explicitly request this skill. |
| `disable-auto-invoke` | boolean | `false` | Whether the agent should avoid automatic invocation. |
| `argument-hint` | string | empty | Short usage hint for user-facing skill lists. |
| `allowed-tools` | list | empty | Optional allow-list for the skill run backend. Empty means no extra restriction. |
| `blocked-tools` | list | empty | Optional deny-list for the skill run backend. |
| `tags` | list | empty | UI and routing labels. |

`allowed-tools` and `blocked-tools` are restrictions, not permission grants. In the current runtime, `mode="run"` can only use `execute_office_shell`, and that command still runs inside the office sandbox.
```

- [ ] **Step 2: Review docs diff**

Run: `git diff -- docs/tools.md`

Expected: Diff contains only the new skill metadata documentation section.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/tools.md
git commit -m "docs: document skill metadata"
```

### Task 6: Final Verification

**Files:**
- No planned edits.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: confidence that loader, policy-adjacent behavior, client build, and existing tests are not broken.

- [ ] **Step 1: Run backend test suite**

Run: `python3 -m pytest tests/test_skill_loader.py tests/test_config_and_skill_loader.py tests/test_policy.py tests/test_two_phase_skills.py -q`

Expected: PASS.

- [ ] **Step 2: Run frontend build/typecheck**

Run: `cd client && npm run build`

Expected: PASS, or capture exact environment failure and run `cd client && npx tsc --noEmit` as fallback.

- [ ] **Step 3: Inspect working tree**

Run: `git status --short`

Expected: Only pre-existing unrelated changes remain. New task changes should be committed.

