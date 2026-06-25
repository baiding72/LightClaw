"""Tests migrated from CyberClaw's lazy skill loader and two-stage skill idea."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage

from core.agent import create_agent_harness
from tests.test_mvp_learning import QueueChatModel


def _write_skill(root: Path, folder: str = "safe_echo", name: str = "safe_echo") -> Path:
    skill_dir = root / folder
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"""name: {name}
description: Safe echo skill for tests

# Safe Echo

This skill can safely echo short text.

Use:

```bash
echo skill-ok
```
""",
        encoding="utf-8",
    )
    return skill_md


def test_lazy_skill_loader_scans_metadata_and_loads_help(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "office" / "skills"
    _write_skill(skills_dir)
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)
    skill_loader.clear_skill_cache()

    assert skill_loader.get_skill_count() == 1
    tools = skill_loader.load_dynamic_skills()

    assert len(tools) == 1
    assert tools[0].name == "safe_echo"
    assert "First call mode='help'" in tools[0].description

    result = tools[0].invoke({"mode": "help"})
    assert "Safe Echo" in result
    assert "mode='run'" in result


def test_lazy_skill_loader_reload_picks_up_new_skill(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "office" / "skills"
    _write_skill(skills_dir, folder="one", name="one")
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)
    skill_loader.clear_skill_cache()

    assert skill_loader.get_skill_count() == 1
    _write_skill(skills_dir, folder="two", name="two")

    tools = skill_loader.reload_skills()
    assert {tool.name for tool in tools} == {"one", "two"}


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


def test_two_stage_skill_runs_inside_react_loop(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "office" / "skills"
    _write_skill(skills_dir, name="safe_echo")
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)
    skill_loader.clear_skill_cache()
    tools = skill_loader.load_dynamic_skills(force_rescan=True)

    llm = QueueChatModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"id": "help_1", "name": "safe_echo", "args": {"mode": "help"}}],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "run_1", "name": "safe_echo", "args": {"mode": "run", "command": "echo skill-ok"}}
                ],
            ),
            AIMessage(content="skill completed"),
        ]
    )
    harness = create_agent_harness(llm, tools=tools, max_turns=5)

    result = harness.run("use safe echo")

    tool_messages = [message for message in result["state"].messages if message.role == "tool"]
    assert len(tool_messages) == 2
    assert "Safe Echo" in tool_messages[0].content
    assert "skill-ok" in tool_messages[1].content
    assert result["answer"] == "skill completed"
