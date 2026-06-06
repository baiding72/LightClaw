"""Sandboxed file tools for myClaw - Custom implementation."""

from __future__ import annotations

from pathlib import Path

from core.tools.base import tool


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFICE_DIR = PROJECT_ROOT / "workspace" / "office"
MAX_READ_CHARS = 8000


def _safe_path(relative_path: str) -> Path:
    if not relative_path or not relative_path.strip():
        raise ValueError("relative_path is required")

    office_root = OFFICE_DIR.resolve()
    raw_path = Path(relative_path)
    if raw_path.is_absolute():
        candidate = raw_path.resolve()
    else:
        normalized = relative_path.strip()
        prefix = "workspace/office/"
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
        candidate = (OFFICE_DIR / normalized).resolve()
    if candidate != office_root and office_root not in candidate.parents:
        raise ValueError("path escapes the myClaw office sandbox")
    return candidate


@tool
def list_office_files(relative_path: str = ".") -> str:
    """List files under the myClaw office sandbox.

    Args:
        relative_path: Directory path relative to the office sandbox.

    Returns:
        A newline-separated directory listing.
    """
    try:
        path = _safe_path(relative_path)
        OFFICE_DIR.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            return f"Error: path does not exist: {relative_path}"
        if not path.is_dir():
            return f"Error: path is not a directory: {relative_path}"

        entries = []
        for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            suffix = "/" if item.is_dir() else ""
            entries.append(f"{item.relative_to(OFFICE_DIR)}{suffix}")
        return "\n".join(entries) if entries else "(empty)"
    except Exception as exc:
        return f"Error: {exc}"


@tool
def read_office_file(relative_path: str) -> str:
    """Read a UTF-8 text file from the myClaw office sandbox.

    Args:
        relative_path: File path relative to the office sandbox.

    Returns:
        File contents, truncated when the file is large.
    """
    try:
        path = _safe_path(relative_path)
        if not path.exists():
            return f"Error: file does not exist: {relative_path}"
        if not path.is_file():
            return f"Error: path is not a file: {relative_path}"

        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > MAX_READ_CHARS:
            return content[:MAX_READ_CHARS] + "\n...[truncated]"
        return content
    except Exception as exc:
        return f"Error: {exc}"


@tool
def write_office_file(relative_path: str, content: str) -> str:
    """Create a UTF-8 text file inside the myClaw office sandbox.

    Args:
        relative_path: File path relative to the office sandbox.
        content: Text content to write.

    Returns:
        A short confirmation message.
    """
    try:
        path = _safe_path(relative_path)
        OFFICE_DIR.mkdir(parents=True, exist_ok=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return f"Error: file already exists: {relative_path}. Use update_office_file for existing files."
        path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {path.relative_to(OFFICE_DIR)}"
    except Exception as exc:
        return f"Error: {exc}"


@tool
def update_office_file(relative_path: str, content: str) -> str:
    """Update an existing UTF-8 text file inside the myClaw office sandbox.

    Args:
        relative_path: File path relative to the office sandbox.
        content: Replacement text content.

    Returns:
        A short confirmation message.
    """
    try:
        path = _safe_path(relative_path)
        if not path.exists():
            return f"Error: file does not exist: {relative_path}. Use write_office_file for new files."
        if not path.is_file():
            return f"Error: path is not a file: {relative_path}"
        path.write_text(content, encoding="utf-8")
        return f"Updated {len(content)} characters in {path.relative_to(OFFICE_DIR)}"
    except Exception as exc:
        return f"Error: {exc}"


FILE_TOOLS = [list_office_files, read_office_file, write_office_file, update_office_file]
