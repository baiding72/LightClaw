"""Local source retrieval for project, notes, and traces.

This is intentionally lightweight. It gives source routing a real local lookup
surface before we introduce embeddings or a database-backed retriever.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

from core.config import MEMORY_DIR

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MYCLAW_DIR = PROJECT_ROOT
OFFICE_DIR = MYCLAW_DIR / "workspace" / "office"
DOCS_DIR = MYCLAW_DIR / "docs"
NOTES_DIR = MEMORY_DIR
PROFILE_FILE = MEMORY_DIR / "profile.md"


@dataclass(frozen=True)
class LocalSearchHit:
    source_type: str
    path: str
    title: str
    score: float
    preview: str

    def to_trace(self) -> dict[str, object]:
        return {
            "source_type": self.source_type,
            "path": self.path,
            "title": self.title,
            "score": round(self.score, 3),
            "preview": self.preview[:240],
        }


def _tokens(query: str) -> set[str]:
    lowered = query.lower()
    ascii_tokens = set(re.findall(r"[a-z0-9_./-]{2,}", lowered))
    cjk_tokens = {part for part in re.split(r"[，。！？；：、\s]+", query) if len(part) >= 2}
    keywords = {
        "myclaw",
        "cyberclaw",
        "trace",
        "badcase",
        "memory",
        "profile",
        "note",
        "工具",
        "记忆",
        "评测",
        "约束",
        "权限",
        "会话",
        "项目",
        "文件",
    }
    return {token for token in ascii_tokens | cjk_tokens | keywords if token and token.lower() in lowered}


def _score(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    lowered = text.lower()
    hits = sum(1 for token in query_tokens if token.lower() in lowered)
    return hits / max(1, len(query_tokens))


def _preview(text: str, query_tokens: set[str]) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""
    lowered = compact.lower()
    for token in query_tokens:
        index = lowered.find(token.lower())
        if index >= 0:
            start = max(0, index - 80)
            end = min(len(compact), index + 180)
            return compact[start:end]
    return compact[:240]


def _iter_text_files(root: Path, source_type: str) -> list[tuple[str, Path, str]]:
    if not root.exists():
        return []
    allowed_suffixes = {".md", ".txt", ".json", ".jsonl", ".py", ".ts", ".tsx", ".rs"}
    files: list[tuple[str, Path, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        if any(part in {"node_modules", "target", "__pycache__"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        files.append((source_type, path, text[:12000]))
    return files


def _iter_note_files() -> list[tuple[str, Path, str]]:
    files: list[tuple[str, Path, str]] = []
    if PROFILE_FILE.exists():
        try:
            files.append(("memory.profile", PROFILE_FILE, PROFILE_FILE.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            pass
    memory_file = NOTES_DIR / "MEMORY.md"
    if memory_file.exists():
        try:
            files.append(("memory.note", memory_file, memory_file.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            pass
    return files


def search_project_sources(query: str, *, limit: int = 5) -> list[LocalSearchHit]:
    query_tokens = _tokens(query)
    candidates: list[tuple[str, Path, str]] = []
    candidates.extend(_iter_note_files())
    candidates.extend(_iter_text_files(OFFICE_DIR, "office.file"))
    candidates.extend(_iter_text_files(DOCS_DIR, "docs"))

    hits: list[LocalSearchHit] = []
    for source_type, path, text in candidates:
        score = _score(query_tokens, f"{path.name}\n{text}")
        if score <= 0:
            continue
        try:
            display_path = str(path.relative_to(PROJECT_ROOT))
        except ValueError:
            display_path = str(path)
        hits.append(
            LocalSearchHit(
                source_type=source_type,
                path=display_path,
                title=path.name,
                score=score,
                preview=_preview(text, query_tokens),
            )
        )
    hits.sort(key=lambda hit: (-hit.score, hit.source_type, hit.path))
    return hits[: max(1, limit)]
