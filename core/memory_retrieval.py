"""Small in-process ranking helpers for file-backed memory notes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Any


@dataclass(frozen=True)
class RankedMemoryNote:
    note: dict[str, str]
    score: float
    matched_terms: tuple[str, ...]


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    ascii_tokens = re.findall(r"[a-z0-9_./-]{2,}", lowered)
    cjk_tokens = re.findall(r"[\u4e00-\u9fff]", text)
    return ascii_tokens + cjk_tokens


def _term_counts(tokens: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[key] * b[key] for key in common)
    na = math.sqrt(sum(value * value for value in a.values()))
    nb = math.sqrt(sum(value * value for value in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _recency_boost(note: dict[str, str]) -> float:
    updated = _parse_time(note.get("updated_at", ""))
    if not updated:
        return 0.0
    age_days = max(0.0, (datetime.now(timezone.utc) - updated).total_seconds() / 86400.0)
    return 0.08 * math.exp(-age_days / 30.0)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def rank_memory_notes(query: str, notes: list[dict[str, str]], *, limit: int = 5) -> list[RankedMemoryNote]:
    """Rank notes with TF-IDF-ish cosine, title boost, recency, and MMR diversity."""
    query_tokens = tokenize(query)
    if not query_tokens or not notes:
        return []

    docs = [f"{note.get('title', '')}\n{note.get('content', '')}" for note in notes]
    doc_tokens = [tokenize(doc) for doc in docs]
    n_docs = len(docs)
    df: dict[str, int] = {}
    for tokens in doc_tokens:
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1

    def vector(tokens: list[str]) -> dict[str, float]:
        counts = _term_counts(tokens)
        return {
            token: count * (math.log((n_docs + 1) / (df.get(token, 0) + 1)) + 1.0)
            for token, count in counts.items()
        }

    query_vec = vector(query_tokens)
    query_set = set(query_tokens)
    scored: list[RankedMemoryNote] = []
    for note, tokens in zip(notes, doc_tokens):
        token_set = set(tokens)
        matched = tuple(sorted(query_set & token_set))
        if not matched:
            continue
        score = _cosine(query_vec, vector(tokens))
        title_tokens = set(tokenize(note.get("title", "")))
        if query_set & title_tokens:
            score += 0.18
        score += _recency_boost(note)
        if score > 0:
            scored.append(RankedMemoryNote(note=note, score=score, matched_terms=matched))

    scored.sort(key=lambda item: item.score, reverse=True)
    selected: list[RankedMemoryNote] = []
    remaining = list(scored)
    while remaining and len(selected) < max(1, limit):
        best_index = 0
        best_value = float("-inf")
        selected_sets = [set(tokenize(f"{item.note.get('title', '')}\n{item.note.get('content', '')}")) for item in selected]
        for index, item in enumerate(remaining):
            item_set = set(tokenize(f"{item.note.get('title', '')}\n{item.note.get('content', '')}"))
            diversity_penalty = max((_jaccard(item_set, selected_set) for selected_set in selected_sets), default=0.0)
            mmr_score = 0.75 * item.score - 0.25 * diversity_penalty
            if mmr_score > best_value:
                best_value = mmr_score
                best_index = index
        selected.append(remaining.pop(best_index))
    return selected


def format_ranked_notes(query: str, ranked: list[RankedMemoryNote]) -> str:
    if not ranked:
        return f"No notes found matching: {query}"
    lines = [f"Found {len(ranked)} note(s), ranked by lightweight memory retrieval:"]
    for item in ranked:
        note = item.note
        lines.append(
            f"- [{note['id']}] {note['title']} "
            f"(score: {item.score:.3f}, matched: {', '.join(item.matched_terms[:8])}, "
            f"updated: {note.get('updated_at', 'unknown')[:10]})"
        )
    return "\n".join(lines)
