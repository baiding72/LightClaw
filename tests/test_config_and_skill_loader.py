"""CyberClaw config/skill-loader tests migrated to myClaw."""

from __future__ import annotations


def test_config_paths_exist_and_are_path_objects():
    from pathlib import Path

    from core.config import (
        APPROVALS_DIR,
        CONFIG_DIR,
        MEMORY_DIR,
        MYCLAW_DIR,
        OFFICE_DIR,
        PROJECT_ROOT,
        RUNTIME_DIR,
        SKILLS_DIR,
        TASKS_FILE,
        WORKSPACE_DIR,
    )

    for path in [PROJECT_ROOT, MYCLAW_DIR, WORKSPACE_DIR, OFFICE_DIR, SKILLS_DIR, MEMORY_DIR, CONFIG_DIR, RUNTIME_DIR, APPROVALS_DIR, TASKS_FILE]:
        assert isinstance(path, Path)

    assert OFFICE_DIR.exists()
    assert SKILLS_DIR.exists()


def test_skill_loader_imports():
    from core.skill_loader import clear_skill_cache, get_skill_count, load_dynamic_skills, reload_skills

    assert callable(load_dynamic_skills)
    assert callable(reload_skills)
    assert callable(get_skill_count)
    assert callable(clear_skill_cache)


def test_load_dynamic_skills_missing_directory_returns_empty(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    monkeypatch.setattr(skill_loader, "SKILLS_DIR", tmp_path / "missing")
    skill_loader.clear_skill_cache()

    assert skill_loader.load_dynamic_skills(force_rescan=True) == []
    assert skill_loader.get_skill_count() == 0


def test_load_dynamic_skills_empty_directory_returns_empty(tmp_path, monkeypatch):
    import core.skill_loader as skill_loader

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", skills_dir)
    skill_loader.clear_skill_cache()

    assert skill_loader.load_dynamic_skills(force_rescan=True) == []
    assert skill_loader.get_skill_count() == 0

