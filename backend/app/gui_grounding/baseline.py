"""
Rule-based GUI grounding baseline.

This is not a full GUI agent. It provides a deterministic selector/bbox baseline
for evaluation and data export tests.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field


class CandidateBox(BaseModel):
    candidate_id: str
    selector: str | None = None
    text: str = ""
    role: str | None = None
    bbox: tuple[float, float, float, float]
    context: str = ""

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)


class GroundingInput(BaseModel):
    instruction: str
    candidates: list[CandidateBox] = Field(default_factory=list)
    screenshot_metadata: dict = Field(default_factory=dict)


class GroundingPrediction(BaseModel):
    candidate_id: str | None = None
    selector: str | None = None
    point: tuple[float, float] | None = None
    bbox: tuple[float, float, float, float] | None = None
    confidence: float = 0.0
    rationale: str = ""


class GroundingLabel(BaseModel):
    candidate_id: str | None = None
    selector: str | None = None
    bbox: tuple[float, float, float, float]


def _tokens(text: str) -> set[str]:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())
    return {token for token in normalized.split() if token}


class RuleBasedGroundingModule:
    """Lexical matching baseline over DOM candidates."""

    def predict(self, request: GroundingInput) -> GroundingPrediction:
        if not request.candidates:
            return GroundingPrediction(rationale="No candidates were provided.")

        instruction_tokens = _tokens(request.instruction)
        best: tuple[float, CandidateBox] | None = None
        for candidate in request.candidates:
            haystack = " ".join(
                part for part in [candidate.text, candidate.role or "", candidate.context, candidate.selector or ""]
                if part
            )
            candidate_tokens = _tokens(haystack)
            overlap = len(instruction_tokens & candidate_tokens)
            role_bonus = 0.25 if candidate.role and candidate.role.lower() in request.instruction.lower() else 0.0
            text_bonus = 0.5 if candidate.text and candidate.text in request.instruction else 0.0
            score = overlap + role_bonus + text_bonus
            if best is None or score > best[0]:
                best = (score, candidate)

        assert best is not None
        score, candidate = best
        confidence = min(1.0, score / max(len(instruction_tokens), 1))
        return GroundingPrediction(
            candidate_id=candidate.candidate_id,
            selector=candidate.selector,
            point=candidate.center,
            bbox=candidate.bbox,
            confidence=confidence,
            rationale=f"Matched candidate by lexical overlap score={score:.2f}.",
        )
