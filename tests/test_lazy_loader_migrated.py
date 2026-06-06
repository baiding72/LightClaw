"""Migrated lazy skill loader tests from CyberClaw."""

from __future__ import annotations

from pathlib import Path

from core import skill_loader as skill_loader_module


def _create_skill(root: Path, folder: str, name: str, description: str, body: str = "") -> None:
    skill_dir = root / folder
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"""name: {name}
description: {description}

## Manual

{body or "Use mode='help' before mode='run'."}
""",
        encoding="utf-8",
    )


def test_lazy_skill_loader_scans_metadata_without_full_run(monkeypatch, tmp_path):
    skills_dir = tmp_path / "office" / "skills"
    _create_skill(skills_dir, "skill_a", "Skill A", "First test skill", "A manual")
    _create_skill(skills_dir, "skill_b", "Skill B", "Second test skill", "B manual")
    monkeypatch.setattr(skill_loader_module, "SKILLS_DIR", skills_dir)
    skill_loader_module.clear_skill_cache()

    tools = skill_loader_module.load_dynamic_skills(force_rescan=True)

    assert skill_loader_module.get_skill_count() == 2
    assert [tool.name for tool in tools] == ["Skill_A", "Skill_B"]
    assert "First test skill" in tools[0].description
    assert "First call mode='help'" in tools[0].description


def test_lazy_skill_loader_loads_manual_on_help_and_reloads_new_skills(monkeypatch, tmp_path):
    skills_dir = tmp_path / "office" / "skills"
    _create_skill(skills_dir, "skill_a", "Skill A", "First test skill", "A full manual")
    monkeypatch.setattr(skill_loader_module, "SKILLS_DIR", skills_dir)
    skill_loader_module.clear_skill_cache()

    tools = skill_loader_module.load_dynamic_skills(force_rescan=True)
    help_text = tools[0].invoke({"mode": "help"})

    assert "Skill A manual" in help_text
    assert "A full manual" in help_text

    _create_skill(skills_dir, "skill_b", "Skill B", "Second test skill", "B full manual")
    reloaded_tools = skill_loader_module.reload_skills()

    assert [tool.name for tool in reloaded_tools] == ["Skill_A", "Skill_B"]


def test_lazy_skill_loader_run_requires_command(monkeypatch, tmp_path):
    skills_dir = tmp_path / "office" / "skills"
    _create_skill(skills_dir, "skill_a", "Skill A", "First test skill")
    monkeypatch.setattr(skill_loader_module, "SKILLS_DIR", skills_dir)
    skill_loader_module.clear_skill_cache()

    tool = skill_loader_module.load_dynamic_skills(force_rescan=True)[0]

    assert "command is required" in tool.invoke({"mode": "run"})
    assert "mode must be" in tool.invoke({"mode": "unknown"})
