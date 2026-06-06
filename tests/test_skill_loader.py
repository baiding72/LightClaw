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

