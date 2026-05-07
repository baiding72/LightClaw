"""Recruiting-specific evaluation metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.recruiting.extractor import ApplyStep, JobPosting
from app.schemas.action import StopReason


def calculate_recruiting_metrics(output_dir: Path) -> dict[str, Any]:
    traces = _read_jsonl(output_dir / "traces.jsonl")
    jobs = [JobPosting.model_validate(row) for row in _read_jsonl(output_dir / "extracted_jobs.jsonl")]
    steps = [ApplyStep.model_validate(row) for row in _read_jsonl(output_dir / "apply_flow_steps.jsonl")]

    stop_reasons = [row.get("stop_reason") for row in traces if row.get("stop_reason")]
    stop_reason_distribution: dict[str, int] = {}
    for reason in stop_reasons:
        stop_reason_distribution[reason] = stop_reason_distribution.get(reason, 0) + 1
    safe_stops = [
        reason for reason in stop_reasons
        if reason in {
            StopReason.LOGIN_REQUIRED.value,
            StopReason.CAPTCHA_BLOCKED.value,
            StopReason.SAFE_STOP.value,
            StopReason.TASK_COMPLETED.value,
        }
    ]
    schema_rows = len(jobs) + len(steps)
    return {
        "jobs_extracted_count": len(jobs),
        "apply_flow_steps_count": len(steps),
        "blocked_by_login": any(reason == StopReason.LOGIN_REQUIRED.value for reason in stop_reasons),
        "blocked_by_captcha": any(reason == StopReason.CAPTCHA_BLOCKED.value for reason in stop_reasons),
        "safe_stop_count": stop_reason_distribution.get(StopReason.SAFE_STOP.value, 0),
        "stop_reason_distribution": stop_reason_distribution,
        "safe_stop_rate": len(safe_stops) / len(stop_reasons) if stop_reasons else 0.0,
        "extraction_schema_pass_rate": 1.0 if schema_rows else 0.0,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
