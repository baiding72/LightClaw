"""Built-in tools for myClaw - Custom implementation."""

from datetime import datetime
import threading
import urllib.request
import urllib.parse
import json
import re
import os
import uuid
import hashlib
import subprocess
import platform
from pathlib import Path
from typing import Any

from core.config import MEMORY_DIR
from core.memory_retrieval import format_ranked_notes, rank_memory_notes
from core.tools.base import BaseTool, tool


# ============================================
# P0: Core Tools (already implemented)
# ============================================

@tool
def get_time() -> str:
    """Get the current local time.

    Returns:
        Current datetime as a formatted string.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple math expression.

    Args:
        expression: A simple math expression (e.g., "1+1", "2*3").

    Returns:
        The result of the evaluation as a string.
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@tool
def echo(message: str) -> str:
    """Echo back the input message (for testing).

    Args:
        message: The message to echo.

    Returns:
        The same message that was passed in.
    """
    return f"Echo: {message}"


# ============================================
# P1: Web Tools (already implemented)
# ============================================

def _validate_url(url: str) -> str:
    """Validate and normalize URL."""
    if not url:
        raise ValueError("URL cannot be empty")
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    return url


def _truncate_content(content: str, max_chars: int = 8000) -> str:
    """Truncate content to prevent token overflow."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + f"\n\n...[Content truncated, total {len(content)} chars]..."


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        Search results as a formatted string with titles and URLs.
    """
    try:
        encoded_query = urllib.parse.quote(query)
        # Use DuckDuckGo HTML lite interface (no API key needed)
        url = f"https://duckduckgo.com/html/?q={encoded_query}&s-count={max_results}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="replace")

        # Parse results from DuckDuckGo HTML
        results = []

        # Pattern 1: result__a class with full URL (rel=nofollow links)
        # These are actual search results with "DuckDuckGo" redirect URLs
        pattern1 = r'<a[^>]*rel="nofollow"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern1, html)

        seen_urls = set()
        for raw_url, title in matches:
            # Decode the DuckDuckGo redirect URL
            if "uddg=" in raw_url:
                try:
                    # Extract the actual URL from the redirect
                    parsed = urllib.parse.urlparse(raw_url)
                    params = urllib.parse.parse_qs(parsed.query)
                    if "uddg" in params:
                        actual_url = params["uddg"][0]
                    else:
                        actual_url = raw_url
                except Exception:
                    actual_url = raw_url
            else:
                actual_url = raw_url

            # Clean title
            title = re.sub(r'<[^>]+>', '', title).strip()
            if not title or len(title) < 3:
                continue
            if actual_url in seen_urls:
                continue
            seen_urls.add(actual_url)

            results.append(f"- {title}: {actual_url}")
            if len(results) >= max_results:
                break

        # Fallback pattern: try to find URLs directly in text
        if not results:
            url_pattern = r'(https?://(?:www\.)?(?:python\.org|w3schools\.com|geeksforgeeks\.org|programiz\.com|learnpython\.org|realpython\.com)[^\s"<>]+)'
            url_matches = re.findall(url_pattern, html, re.IGNORECASE)
            for url_found in url_matches[:max_results]:
                results.append(f"- [Result]: {url_found}")

        if not results:
            return f"No search results found for: {query}"

        return f"Search results for '{query}':\n" + "\n".join(results)

    except urllib.error.URLError as e:
        return f"Search failed (network error): {e}"
    except Exception as e:
        return f"Search failed: {e}"


@tool
def read_url(url: str) -> str:
    """Read the content of a web page.

    Args:
        url: The URL to fetch content from.

    Returns:
        The text content of the page (truncated if too large).
    """
    try:
        url = _validate_url(url)

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            content_type = response.headers.get("Content-Type", "")
            html = response.read().decode("utf-8", errors="replace")

        # Extract text from HTML
        text = _extract_text_from_html(html)

        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return _truncate_content(text)

    except urllib.error.HTTPError as e:
        return f"Failed to fetch URL (HTTP {e.code}): {e.reason}"
    except urllib.error.URLError as e:
        return f"Failed to fetch URL (network error): {e}"
    except ValueError as e:
        return f"Invalid URL: {e}"
    except Exception as e:
        return f"Failed to read URL: {e}"


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML content."""
    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Replace common block elements with newlines
    html = re.sub(r'<(?:div|p|br|h[1-6]|li|tr)[^>]*>', '\n', html, flags=re.IGNORECASE)

    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', '', html)

    # Decode HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')

    # Clean up whitespace
    text = re.sub(r'[ \t]+', ' ', text)

    return text


# ============================================
# P1: Task Scheduling Tools
# ============================================

TASKS_DIR = Path.home() / ".myclaw" / "tasks"
TASKS_FILE = TASKS_DIR / "tasks.json"
_TASKS_LOCK = threading.Lock()


def _load_tasks() -> list[dict[str, Any]]:
    """Load tasks from JSON file (thread-safe)."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    if not TASKS_FILE.exists():
        return []
    try:
        return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_tasks(tasks: list[dict[str, Any]]) -> None:
    """Save tasks to JSON file (thread-safe)."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def _atomic_task_op(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Atomically load, modify, and save tasks under lock."""
    with _TASKS_LOCK:
        current = _load_tasks()
        # Apply changes
        result = tasks(current)
        _save_tasks(result)
        return result


@tool
def schedule_task(target_time: str, description: str, repeat: str = None, repeat_count: int = None) -> str:
    """Schedule a task for a future time.

    Args:
        target_time: Target time in format "YYYY-MM-DD HH:MM:SS" (must be in the future).
        description: The task description or reminder message.
        repeat: Optional. Repeat frequency: "hourly", "daily", "weekly". None for one-time.
        repeat_count: Optional. Number of times to repeat. None for infinite.

    Returns:
        Confirmation message with task details.
    """
    try:
        target_dt = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return f"Error: time format must be YYYY-MM-DD HH:MM:SS, got: {target_time}"

    now = datetime.now()
    if target_dt <= now:
        return f"Error: target_time must be in the future. Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}"

    with _TASKS_LOCK:
        tasks = _load_tasks()
        new_task = {
            "id": str(uuid.uuid4())[:8],
            "target_time": target_time,
            "description": description,
            "repeat": repeat,
            "repeat_count": repeat_count,
            "created_at": datetime.now().isoformat(),
        }
        tasks.append(new_task)
        _save_tasks(tasks)

    msg = f"Task scheduled: [{new_task['id']}] at {target_time} | {description}"
    if repeat:
        msg += f" | repeat: {repeat} ({repeat_count or 'infinite'} times)"
    return msg


@tool
def list_tasks() -> str:
    """List all scheduled tasks.

    Returns:
        Formatted list of pending tasks, or message if none.
    """
    with _TASKS_LOCK:
        tasks = _load_tasks()
        if not tasks:
            return "No scheduled tasks."

        # Sort by target time (in memory, no file write needed)
        tasks.sort(key=lambda t: t["target_time"])

        lines = ["Pending tasks:"]
        for t in tasks:
            repeat_info = f" (repeats {t.get('repeat', 'none')})" if t.get("repeat") else ""
            lines.append(f"- [{t['id']}] {t['target_time']} | {t['description']}{repeat_info}")

        return "\n".join(lines)


@tool
def cancel_task(task_id: str) -> str:
    """Cancel a scheduled task by its ID.

    Args:
        task_id: The task ID to cancel.

    Returns:
        Confirmation message.
    """
    with _TASKS_LOCK:
        tasks = _load_tasks()
        before = len(tasks)
        tasks = [t for t in tasks if t["id"] != task_id]

        if len(tasks) == before:
            return f"Error: task [{task_id}] not found."

        _save_tasks(tasks)
    return f"Task [{task_id}] cancelled."


@tool
def modify_task(task_id: str, new_time: str = None, new_description: str = None) -> str:
    """Modify a scheduled task's time or description.

    Args:
        task_id: The task ID to modify.
        new_time: Optional new time in "YYYY-MM-DD HH:MM:SS" format.
        new_description: Optional new description.

    Returns:
        Confirmation message.
    """
    with _TASKS_LOCK:
        tasks = _load_tasks()

        for t in tasks:
            if t["id"] == task_id:
                if new_time:
                    try:
                        target_dt = datetime.strptime(new_time, "%Y-%m-%d %H:%M:%S")
                        now = datetime.now()
                        if target_dt <= now:
                            return f"Error: new_time must be in the future."
                        t["target_time"] = new_time
                    except ValueError:
                        return f"Error: time format must be YYYY-MM-DD HH:MM:SS"
                if new_description:
                    t["description"] = new_description
                _save_tasks(tasks)
                return f"Task [{task_id}] updated."
                break
        else:
            return f"Error: task [{task_id}] not found."


# ============================================
# P1: Note/Memory Tools
# ============================================

NOTES_DIR = MEMORY_DIR
PROFILE_FILE = MEMORY_DIR / "profile.md"


def _ensure_notes_dir() -> None:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)


def _project_memory_file() -> Path:
    return NOTES_DIR / "MEMORY.md"


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _content_hash(value: str) -> str:
    return hashlib.sha256(_normalize_text(value).encode("utf-8")).hexdigest()[:16]


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", (value or "").strip().lower()).strip("-")
    return text[:40] or f"memory-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _load_project_notes() -> list[dict[str, str]]:
    _ensure_notes_dir()
    memory_file = _project_memory_file()
    if not memory_file.exists():
        return []
    text = memory_file.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        r"<!--\s*note:id=(?P<id>[^ ]+)\s+title=(?P<title>.*?)\s+hash=(?P<hash>[^ ]+)\s+created=(?P<created>[^ ]+)\s+updated=(?P<updated>[^ ]+)\s*-->\n"
        r"## (?P<heading>.*?)\n\n(?P<content>.*?)(?=\n<!--\s*note:id=|\Z)",
        re.DOTALL,
    )
    notes: list[dict[str, str]] = []
    for match in pattern.finditer(text):
        notes.append(
            {
                "id": match.group("id").strip(),
                "title": match.group("title").strip(),
                "content_hash": match.group("hash").strip(),
                "created_at": match.group("created").strip(),
                "updated_at": match.group("updated").strip(),
                "content": match.group("content").strip(),
            }
        )
    return notes


def _write_project_notes(notes: list[dict[str, str]]) -> None:
    _ensure_notes_dir()
    lines = ["# myClaw Project Memory", ""]
    if not notes:
        lines.append("(empty)")
    for note in notes:
        note_id = str(note["id"])
        title = str(note.get("title") or note_id)
        content = str(note.get("content") or "").strip()
        content_hash = _content_hash(content)
        created = str(note.get("created_at") or datetime.now().isoformat())
        updated = str(note.get("updated_at") or datetime.now().isoformat())
        lines.extend(
            [
                f"<!-- note:id={note_id} title={title} hash={content_hash} created={created} updated={updated} -->",
                f"## {title}",
                "",
                content,
                "",
            ]
        )
    _project_memory_file().write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _profile_keys(content: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip().lstrip("-*").strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = re.sub(r"\s+", "", key.strip().lower().strip("*"))
        if normalized_key:
            keys[normalized_key] = value.strip()
    return keys


def _parse_flat_profile_json(text: str) -> tuple[str, str | None] | None:
    if not text.startswith(("{", "[")):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return "", "Error: user profile content must be Markdown text or a flat JSON object."
    lines: list[str] = []
    for key, value in parsed.items():
        if isinstance(value, (dict, list)):
            return "", "Error: user profile JSON must be flat; use concise Markdown bullet lines for complex content."
        rendered = json.dumps(value, ensure_ascii=False) if isinstance(value, bool) or value is None else str(value)
        lines.append(f"- {key}: {rendered}")
    if not lines:
        return "", "Error: user profile content cannot be empty."
    return "\n".join(lines), None


def _strip_profile_memory_wrappers(text: str) -> str:
    """Remove generic remember wrappers before validating profile content."""
    stripped = text.strip()
    if "\n" in stripped:
        return stripped
    stripped = re.sub(r"^[-*]\s*(?:用户偏好|user preference)\s*[:：]\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"^(?:请记住|记住)\s*[:：]\s*", "", stripped)
    return stripped.strip()


def _markdownize_profile_line(text: str) -> str:
    stripped = text.strip()
    if "\n" in stripped:
        return text
    if stripped.startswith(("- ", "* ")):
        return text
    if "：" in stripped and ":" not in stripped:
        key, value = stripped.split("：", 1)
        if key.strip() and value.strip():
            return f"- {key.strip()}: {value.strip()}"
    return text


def _normalize_profile_content(new_content: str) -> tuple[str, str | None]:
    """Keep profile.md human-readable even if the model passes flat JSON."""
    text = (new_content or "").strip()
    if not text:
        return text, None
    parsed = _parse_flat_profile_json(text)
    if parsed is not None:
        return parsed

    unwrapped = _strip_profile_memory_wrappers(text)
    parsed = _parse_flat_profile_json(unwrapped)
    if parsed is not None:
        return parsed
    if unwrapped != text:
        return _markdownize_profile_line(unwrapped), None
    return _markdownize_profile_line(new_content), None


def _load_note_file(note_id: str) -> tuple[Path, dict[str, Any]]:
    _ensure_notes_dir()
    for note in _load_project_notes():
        if note["id"] == note_id:
            return _project_memory_file(), note
    legacy_file = NOTES_DIR / f"{note_id}.json"
    if legacy_file.exists():
        data = json.loads(legacy_file.read_text(encoding="utf-8"))
        return legacy_file, data
    raise ValueError(f"Note [{note_id}] not found.")


@tool
def save_note(content: str = "", title: str = None, action: str = "append", note_id: str = None) -> str:
    """Create, edit, delete, or clear project memory in one MEMORY.md file.

    Args:
        content: Note content for append/edit.
        title: Optional title for append/edit.
        action: append, edit, delete, or clear.
        note_id: Required for edit/delete.

    Returns:
        Confirmation message with note ID.
    """
    _ensure_notes_dir()
    normalized_action = (action or "append").strip().lower()
    if normalized_action not in {"append", "edit", "delete", "clear"}:
        return "Error: action must be one of: append, edit, delete, clear."
    notes = _load_project_notes()
    if normalized_action == "clear":
        _write_project_notes([])
        return "Project memory cleared."
    if normalized_action in {"edit", "delete"} and not note_id:
        return f"Error: action={normalized_action} requires note_id."
    if normalized_action == "delete":
        next_notes = [note for note in notes if note["id"] != note_id]
        if len(next_notes) == len(notes):
            return f"Note [{note_id}] not found."
        _write_project_notes(next_notes)
        return f"Note deleted: [{note_id}]"
    if not content or not content.strip():
        return "Error: note content cannot be empty."
    incoming_hash = _content_hash(content)
    if normalized_action == "append":
        for existing in notes:
            if existing.get("content_hash") == incoming_hash or _normalize_text(existing.get("content", "")) == _normalize_text(content):
                return f"Note already exists: [{existing.get('id')}] {existing.get('title')}. Use save_note(action='edit') for changes."
        next_id = f"{_slug(title or content[:30])}-{str(uuid.uuid4())[:6]}"
        next_title = title or f"note-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        notes.append(
            {
                "id": next_id,
                "title": next_title,
                "content": content,
                "content_hash": incoming_hash,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        )
        _write_project_notes(notes)
        return f"Note saved: [{next_id}] {next_title} ({len(content)} chars)"
    for note in notes:
        if note["id"] == note_id:
            previous_title = note.get("title") or note_id
            if _normalize_text(note.get("content", "")) == _normalize_text(content) and (not title or title == previous_title):
                return "Note unchanged; content already present."
            note["title"] = title or previous_title
            note["content"] = content
            note["content_hash"] = incoming_hash
            note["updated_at"] = datetime.now().isoformat()
            _write_project_notes(notes)
            return f"Note updated: [{note_id}] {note['title']} ({len(content)} chars)"
    return f"Note [{note_id}] not found."


@tool
def search_notes(keyword: str) -> str:
    """Search saved notes with lightweight TF-IDF/recency/MMR ranking.

    Args:
        keyword: Keyword to search for in note titles and content.

    Returns:
        List of matching notes with IDs and titles.
    """
    _ensure_notes_dir()

    ranked = rank_memory_notes(keyword, _load_project_notes(), limit=5)
    return format_ranked_notes(keyword, ranked)


@tool
def read_note(note_id: str = None, keyword: str = None) -> str:
    """Read a specific note by ID or the first note matching a keyword.

    Args:
        note_id: The note ID to read.
        keyword: Alternative to note_id - reads first note matching keyword.

    Returns:
        Note content or error message.
    """
    _ensure_notes_dir()

    if note_id:
        try:
            _, data = _load_note_file(note_id)
            return f"# {data['title']}\n\n{data['content']}"
        except Exception as e:
            return f"Error reading note: {e}"
    elif keyword:
        for data in _load_project_notes():
            if keyword.lower() in str(data.get("content", "")).lower() or keyword.lower() in str(data.get("title", "")).lower():
                return f"# {data['title']}\n\n{data['content']}"
        return f"No notes found matching: {keyword}"
    else:
        return "Error: must provide either note_id or keyword."


@tool
def save_user_profile(new_content: str, action: str = "merge") -> str:
    """Create, merge, replace, or remove content from the single user profile file.

    Args:
        new_content: Profile patch, full replacement content, or removal target.
        action: merge appends a dated update; replace overwrites profile.md; remove removes matching lines.

    Returns:
        Confirmation message.
    """
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not new_content or not new_content.strip():
        return "Error: user profile content cannot be empty."
    new_content, normalize_error = _normalize_profile_content(new_content)
    if normalize_error:
        return normalize_error
    existing = PROFILE_FILE.read_text(encoding="utf-8") if PROFILE_FILE.exists() else ""
    normalized_action = (action or "merge").strip().lower()
    if normalized_action not in {"merge", "replace", "remove"}:
        return "Error: action must be one of: merge, replace, remove."
    if normalized_action == "replace":
        next_content = new_content
    elif normalized_action == "remove":
        target = new_content.strip()
        kept = [line for line in existing.splitlines() if target not in line]
        next_content = "\n".join(kept).strip() + ("\n" if kept else "")
        if next_content.strip() == existing.strip():
            return "User profile unchanged; removal target not found."
    else:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not existing.strip():
            next_content = new_content
        elif new_content.strip() in existing:
            return "User profile unchanged; content already present."
        else:
            existing_keys = _profile_keys(existing)
            incoming_keys = _profile_keys(new_content)
            conflicts = [
                key
                for key, value in incoming_keys.items()
                if key in existing_keys and existing_keys[key] and existing_keys[key] != value
            ]
            conflict_note = ""
            if conflicts:
                conflict_note = "\n\n<!-- myClaw conflict notice: possible profile key conflict: " + ", ".join(conflicts) + " -->"
            next_content = f"{existing.rstrip()}\n\n## Update {stamp}\n{new_content.strip()}{conflict_note}\n"
    PROFILE_FILE.write_text(next_content, encoding="utf-8")
    verb = "updated" if existing.strip() else "saved"
    return f"User profile {verb} ({len(next_content)} chars)."


@tool
def read_user_profile() -> str:
    """Read the user's profile/preferences.

    Returns:
        Profile content or message if none exists.
    """
    if not PROFILE_FILE.exists():
        return "No user profile found."
    return PROFILE_FILE.read_text(encoding="utf-8")


# ============================================
# P1: System Info Tools
# ============================================

@tool
def get_system_info() -> str:
    """Get current system and model information.

    Returns:
        System info including OS, Python version, and configured model.
    """
    info = []
    info.append(f"OS: {platform.system()} {platform.release()}")
    info.append(f"Python: {platform.python_version()}")
    info.append(f"Model: {os.getenv('MYCLAW_MODEL', 'not set')}")
    info.append(f"Provider: {os.getenv('MYCLAW_PROVIDER', 'not set')}")
    return "\n".join(info)


# ============================================
# All P0 + P1 Tools
# ============================================

ALL_TOOLS = [
    # P0: Core
    get_time,
    calculator,
    echo,
    # P0: Web
    web_search,
    read_url,
    # P1: Task Scheduling
    schedule_task,
    list_tasks,
    cancel_task,
    modify_task,
    # P1: Notes/Memory
    save_note,
    search_notes,
    read_note,
    save_user_profile,
    read_user_profile,
    # P1: System
    get_system_info,
]
