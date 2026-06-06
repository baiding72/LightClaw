"""Sandboxed shell execution for myClaw - Custom implementation."""

from __future__ import annotations

import os
import platform
import re
import subprocess
from pathlib import Path

from core.tools.base import tool


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFICE_DIR = PROJECT_ROOT / "workspace" / "office"
SYS_OS = platform.system()

# Shell execution timeout in seconds
SHELL_TIMEOUT = 60
DOCKER_WORKDIR = "/workspace"
DEFAULT_DOCKER_IMAGE = "python:3.12-slim"

# Escape pattern regexes - blocks attempts to escape office sandbox
_ESCAPE_PATTERNS = [
    r"\.\.",                                           # ../ or .. path traversal
    r"(?:^|\s|[<>|&;])/",                              # absolute paths like /etc or cat /file
    r"(?:^|\s|[<>|&;])~",                              # home dir like ~ or ~/.ssh
    r"(?:^|\s|[<>|&;])\\",                              # windows absolute like \ or dir\
    r"(?i)(?:^|\s|[<>|&;])[a-z]:",                     # windows drive like C: or D:
]

# Commands that are never allowed regardless of path
_BLOCKED_COMMANDS = [
    r"^\s*sudo\s",
    r"^\s*su\s",
    r"^\s*chmod\s+777",
    r"^\s*chmod\s+0",
    r"^\s*wget\s+--",  # wget to unknown servers
    r"^\s*curl\s+--",
]


def _check_command_safety(command: str) -> str | None:
    """Check if command tries to escape sandbox. Returns error message or None if safe."""
    # Check escape patterns
    for pattern in _ESCAPE_PATTERNS:
        if re.search(pattern, command):
            return f"Error: detected dangerous directory escape pattern '{pattern}' in command"

    # Check blocked commands
    for pattern in _BLOCKED_COMMANDS:
        if re.match(pattern, command):
            return f"Error: command is not allowed (blocked pattern: {pattern})"

    return None


def _escape_output(text: str, max_chars: int = 2000) -> str:
    """Truncate output to prevent token overflow."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n...[Output truncated, total {len(text)} chars]..."


def _shell_backend() -> str:
    return os.getenv("MYCLAW_SHELL_BACKEND", "local").strip().lower() or "local"


def _docker_image() -> str:
    return os.getenv("MYCLAW_DOCKER_IMAGE", DEFAULT_DOCKER_IMAGE).strip() or DEFAULT_DOCKER_IMAGE


def _format_result(
    *,
    backend: str,
    command: str,
    returncode: int,
    stdout: str,
    stderr: str,
    working_directory: str,
    container_image: str | None = None,
) -> str:
    output = f" ● Current system: {SYS_OS}\n"
    output += f" ● Shell backend: {backend}\n"
    output += f" ● Working directory: {working_directory}\n"
    if container_image:
        output += f" ● Container image: {container_image}\n"
    output += f" ● Command: `{command}`\n"
    output += f" ● Exit code: {returncode}\n"

    stdout = stdout.strip()
    stderr = stderr.strip()

    if returncode != 0 and ("prompt" in stderr.lower() or "y/n" in stdout.lower()):
        output += "\nHint: Command may require confirmation. Use -y or --yes flags."

    if stdout:
        output += f"\n[STDOUT]\n{_escape_output(stdout)}"
    if stderr:
        output += f"\n[STDERR]\n{_escape_output(stderr)}"

    if not stdout and not stderr:
        if returncode == 0:
            output += "\n(Silent execution: no output)"
        else:
            output += "\n(Silent error: no output but non-zero exit)"

    return output


def _run_local_shell(command: str) -> str:
    result = subprocess.run(
        command,
        shell=True,
        cwd=str(OFFICE_DIR),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=SHELL_TIMEOUT,
    )
    return _format_result(
        backend="local",
        command=command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        working_directory=str(OFFICE_DIR),
    )


def _docker_command(command: str) -> list[str]:
    OFFICE_DIR.mkdir(parents=True, exist_ok=True)
    return [
        "docker",
        "run",
        "--rm",
        "--pull",
        os.getenv("MYCLAW_DOCKER_PULL", "missing"),
        "--network",
        os.getenv("MYCLAW_DOCKER_NETWORK", "none"),
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        os.getenv("MYCLAW_DOCKER_MEMORY", "512m"),
        "--cpus",
        os.getenv("MYCLAW_DOCKER_CPUS", "1"),
        "--pids-limit",
        os.getenv("MYCLAW_DOCKER_PIDS", "128"),
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        "--env",
        "HOME=/workspace",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "-v",
        f"{OFFICE_DIR.resolve()}:{DOCKER_WORKDIR}:rw",
        "-w",
        DOCKER_WORKDIR,
        _docker_image(),
        "/bin/sh",
        "-lc",
        command,
    ]


def _run_docker_shell(command: str) -> str:
    try:
        result = subprocess.run(
            _docker_command(command),
            shell=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=SHELL_TIMEOUT,
        )
    except FileNotFoundError:
        return "Error: Docker backend selected, but the docker CLI was not found."

    return _format_result(
        backend="docker",
        command=command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        working_directory=DOCKER_WORKDIR,
        container_image=_docker_image(),
    )


@tool
def execute_office_shell(command: str) -> str:
    """Execute a shell command inside the office sandbox.

    Constraints:
    - Working directory is locked to workspace/office/ (local) or /workspace (docker)
    - Command cannot contain path escape patterns (../, /absolute, ~, \\, C:)
    - Timeout is 60 seconds
    - Only non-interactive commands allowed
    - System is detected automatically (Windows/Linux/Mac)
    - Set MYCLAW_SHELL_BACKEND=docker to run inside a Docker container

    Args:
        command: Shell command to execute (non-interactive).

    Returns:
        Formatted output with exit code and stdout/stderr.
    """
    # Safety check first
    safety_error = _check_command_safety(command)
    if safety_error:
        return f"Error: {safety_error}. Your command is restricted to the office sandbox."

    try:
        backend = _shell_backend()
        if backend == "local":
            return _run_local_shell(command)
        if backend == "docker":
            return _run_docker_shell(command)
        return "Error: unsupported shell backend. Use MYCLAW_SHELL_BACKEND=local or docker."

    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {SHELL_TIMEOUT} seconds. Shell backend: {_shell_backend()}."
    except Exception as exc:
        return f"Error executing command: {exc}"


@tool
def check_office_dir() -> str:
    """Check the office sandbox directory path.

    Returns:
        The resolved office directory path and its current contents.
    """
    try:
        OFFICE_DIR.mkdir(parents=True, exist_ok=True)
        entries = []
        for item in sorted(OFFICE_DIR.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            suffix = "/" if item.is_dir() else ""
            entries.append(f"  {item.name}{suffix}")
        contents = "\n".join(entries) if entries else "(empty)"
        return f"Office sandbox: {OFFICE_DIR}\nShell backend: {_shell_backend()}\nContents:\n{contents}"
    except Exception as exc:
        return f"Error: {exc}"


SHELL_TOOLS = [execute_office_shell, check_office_dir]
