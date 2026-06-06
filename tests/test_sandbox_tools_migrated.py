"""Migrated sandbox tool tests from CyberClaw."""

from __future__ import annotations

from types import SimpleNamespace

from core.tools import files as file_tools
from core.tools import shell as shell_tools


def test_file_tools_stay_inside_office_sandbox(monkeypatch, tmp_path):
    office_dir = tmp_path / "office"
    monkeypatch.setattr(file_tools, "OFFICE_DIR", office_dir)

    write_result = file_tools.write_office_file.invoke(
        {"relative_path": "subdir/file.txt", "content": "sandbox content"}
    )
    read_result = file_tools.read_office_file.invoke({"relative_path": "subdir/file.txt"})
    list_result = file_tools.list_office_files.invoke({"relative_path": "subdir"})

    assert "Wrote 15 characters" in write_result
    assert read_result == "sandbox content"
    assert "subdir/file.txt" in list_result
    assert "escapes" in file_tools.read_office_file.invoke({"relative_path": "../../forbidden.txt"})


def test_write_is_create_only_and_update_is_replace_only(monkeypatch, tmp_path):
    office_dir = tmp_path / "office"
    monkeypatch.setattr(file_tools, "OFFICE_DIR", office_dir)

    assert "Wrote" in file_tools.write_office_file.invoke({"relative_path": "note.md", "content": "v1"})
    assert "already exists" in file_tools.write_office_file.invoke({"relative_path": "note.md", "content": "v2"})
    assert "Updated" in file_tools.update_office_file.invoke({"relative_path": "note.md", "content": "v2"})
    assert file_tools.read_office_file.invoke({"relative_path": "note.md"}) == "v2"
    assert "file does not exist" in file_tools.update_office_file.invoke(
        {"relative_path": "missing.md", "content": "new"}
    )


def test_office_shell_runs_inside_sandbox(monkeypatch, tmp_path):
    office_dir = tmp_path / "office"
    office_dir.mkdir(parents=True)
    monkeypatch.setattr(shell_tools, "OFFICE_DIR", office_dir)

    result = shell_tools.execute_office_shell.invoke({"command": "printf hello > shell.txt && cat shell.txt"})

    assert "Exit code: 0" in result
    assert "hello" in result
    assert (office_dir / "shell.txt").read_text(encoding="utf-8") == "hello"


def test_office_shell_rejects_escape_commands(monkeypatch, tmp_path):
    office_dir = tmp_path / "office"
    office_dir.mkdir(parents=True)
    monkeypatch.setattr(shell_tools, "OFFICE_DIR", office_dir)

    dangerous_commands = [
        "cd ../",
        "cat /etc/passwd",
        "ls ~",
        "dir \\",
        "type C:\\windows\\system32\\config\\sam",
    ]

    for command in dangerous_commands:
        result = shell_tools.execute_office_shell.invoke({"command": command})
        assert result.startswith("Error:")
        assert "office sandbox" in result


def test_office_shell_docker_backend_builds_restricted_container(monkeypatch, tmp_path):
    office_dir = tmp_path / "office"
    office_dir.mkdir(parents=True)
    monkeypatch.setattr(shell_tools, "OFFICE_DIR", office_dir)
    monkeypatch.setenv("MYCLAW_SHELL_BACKEND", "docker")
    monkeypatch.setenv("MYCLAW_DOCKER_IMAGE", "lightclaw-test:latest")

    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="hello\n", stderr="")

    monkeypatch.setattr(shell_tools.subprocess, "run", fake_run)

    result = shell_tools.execute_office_shell.invoke({"command": "printf hello"})

    assert "Shell backend: docker" in result
    assert "Container image: lightclaw-test:latest" in result
    assert "hello" in result

    args, kwargs = calls[0]
    assert args[:3] == ["docker", "run", "--rm"]
    assert kwargs["shell"] is False
    assert ["--pull", "missing"] == args[args.index("--pull"):args.index("--pull") + 2]
    assert ["--network", "none"] == args[args.index("--network"):args.index("--network") + 2]
    assert "--read-only" in args
    assert ["--cap-drop", "ALL"] == args[args.index("--cap-drop"):args.index("--cap-drop") + 2]
    assert ["--security-opt", "no-new-privileges"] == args[
        args.index("--security-opt"):args.index("--security-opt") + 2
    ]
    assert ["--memory", "512m"] == args[args.index("--memory"):args.index("--memory") + 2]
    assert ["--cpus", "1"] == args[args.index("--cpus"):args.index("--cpus") + 2]
    assert ["--pids-limit", "128"] == args[args.index("--pids-limit"):args.index("--pids-limit") + 2]
    assert f"{office_dir.resolve()}:/workspace:rw" in args
    assert args[-4:] == ["lightclaw-test:latest", "/bin/sh", "-lc", "printf hello"]
