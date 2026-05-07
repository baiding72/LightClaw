"""Safe recruiting trajectory collector."""

from __future__ import annotations

import json
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.recruiting.extractor import (
    ApplyStep,
    JobPosting,
    extract_apply_flow,
    extract_job_detail,
    extract_job_list,
    truncate_dom_snapshot,
)
from app.recruiting.guard import RecruitingGuard
from app.schemas.action import AgentAction, AgentActionStatus, AgentActionType, StopReason


def collect_fixture_trajectories(
    fixture_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Collect deterministic recruiting traces from local HTML fixtures."""
    list_html = (fixture_dir / "careers_list.html").read_text(encoding="utf-8")
    detail_html = (fixture_dir / "job_detail.html").read_text(encoding="utf-8")
    apply_html = (fixture_dir / "apply_page.html").read_text(encoding="utf-8")
    captcha_html = (fixture_dir / "apply_captcha_page.html").read_text(encoding="utf-8")
    upload_html = (fixture_dir / "apply_upload_page.html").read_text(encoding="utf-8")
    submit_html = (fixture_dir / "apply_submit_page.html").read_text(encoding="utf-8")

    jobs = extract_job_list(list_html)
    detail = extract_job_detail(detail_html)
    apply_steps = extract_apply_flow(apply_html)
    guard = RecruitingGuard()
    trace_id = f"recruiting_fixture_{uuid.uuid4().hex[:8]}"
    actions: list[dict[str, Any]] = []

    actions.append(_action(
        trace_id=trace_id,
        step=1,
        action_name="open_url",
        page_url="https://fixture.local/careers",
        page_title="Fixture Careers",
        dom_snapshot=list_html,
        extraction_result={"jobs": [job.model_dump() for job in jobs]},
        stop_reason=None,
    ))
    actions.append(_action(
        trace_id=trace_id,
        step=2,
        action_name="extract_jobs",
        page_url="https://fixture.local/careers",
        page_title="Fixture Careers",
        dom_snapshot=list_html,
        extraction_result={"jobs": [job.model_dump() for job in jobs]},
        stop_reason=None,
    ))
    actions.append(_action(
        trace_id=trace_id,
        step=3,
        action_name="click_job",
        page_url=jobs[0].job_url or "https://fixture.local/jobs/llm-intern",
        page_title=detail.page_title or detail.title,
        dom_snapshot=detail_html,
        extraction_result={"job_detail": detail.model_dump()},
        stop_reason=None,
    ))

    guard_result = guard.inspect_page(apply_html)
    stop_reason = guard_result.stop_reason or StopReason.TASK_COMPLETED
    status = AgentActionStatus.BLOCKED if not guard_result.allowed else AgentActionStatus.SUCCESS
    actions.append(_action(
        trace_id=trace_id,
        step=4,
        action_name="extract_apply_flow",
        page_url=detail.apply_url or "https://fixture.local/apply/llm-intern",
        page_title="Fixture Apply",
        dom_snapshot=apply_html,
        extraction_result={"apply_steps": [step.model_dump() for step in apply_steps]},
        stop_reason=stop_reason,
        status=status,
        error_message=None if guard_result.allowed else guard_result.message,
    ))

    extra_steps: list[ApplyStep] = []
    step_index = 5
    for case_name, html, action_name in [
        ("captcha", captcha_html, "detect_captcha"),
        ("file_upload", upload_html, "detect_file_upload"),
        ("submit", submit_html, "submit_application"),
    ]:
        case_steps = extract_apply_flow(html)
        extra_steps.extend(case_steps)
        case_guard = (
            guard.validate_action(action_name, html)
            if case_name == "submit"
            else guard.inspect_page(html)
        )
        actions.append(_action(
            trace_id=trace_id,
            step=step_index,
            action_name=action_name,
            page_url=f"https://fixture.local/apply/{case_name}",
            page_title=f"Fixture Apply {case_name}",
            dom_snapshot=html,
            extraction_result={
                "case": case_name,
                "apply_steps": [step.model_dump() for step in case_steps],
            },
            stop_reason=case_guard.stop_reason or StopReason.TASK_COMPLETED,
            status=AgentActionStatus.BLOCKED if not case_guard.allowed else AgentActionStatus.SUCCESS,
            error_message=None if case_guard.allowed else case_guard.message,
        ))
        step_index += 1

    all_steps = [*apply_steps, *extra_steps]
    _write_outputs(output_dir, actions, jobs, all_steps)
    stop_distribution = _stop_reason_distribution(actions)
    return {
        "trace_id": trace_id,
        "jobs_extracted_count": len(jobs),
        "apply_flow_steps_count": len(all_steps),
        "blocked_by_login": StopReason.LOGIN_REQUIRED.value in stop_distribution,
        "blocked_by_captcha": StopReason.CAPTCHA_BLOCKED.value in stop_distribution,
        "safe_stop_count": stop_distribution.get(StopReason.SAFE_STOP.value, 0),
        "stop_reason_distribution": stop_distribution,
        "safe_stop_rate": _safe_stop_rate(actions),
        "extraction_schema_pass_rate": 1.0,
        "output_dir": str(output_dir),
    }


def collect_dry_run_trajectory(url: str, output_dir: Path) -> dict[str, Any]:
    """Read a real recruiting page in safe dry-run mode.

    This function only opens and extracts. It never logs in, uploads, or submits.
    """
    html = _fetch_html(url)
    guard = RecruitingGuard()
    guard_result = guard.inspect_page(html)
    jobs = extract_job_list(html)
    steps: list[ApplyStep] = [] if not guard_result.allowed else extract_apply_flow(html)
    trace_id = f"recruiting_dry_run_{uuid.uuid4().hex[:8]}"
    stop_reason = guard_result.stop_reason or StopReason.SAFE_STOP
    actions = [
        _action(
            trace_id=trace_id,
            step=1,
            action_name="open_url",
            page_url=url,
            page_title=url,
            dom_snapshot=html,
            extraction_result={"jobs": [job.model_dump() for job in jobs]},
            stop_reason=None,
        ),
        _action(
            trace_id=trace_id,
            step=2,
            action_name="extract",
            page_url=url,
            page_title=url,
            dom_snapshot=html,
            extraction_result={"jobs": [job.model_dump() for job in jobs], "apply_steps": [step.model_dump() for step in steps]},
            stop_reason=stop_reason,
            status=AgentActionStatus.BLOCKED if not guard_result.allowed else AgentActionStatus.SUCCESS,
            error_message=None if guard_result.allowed else guard_result.message,
        ),
    ]
    if guard_result.allowed and jobs and jobs[0].job_url:
        detail_html = _fetch_html(jobs[0].job_url)
        detail_guard = guard.inspect_page(detail_html)
        detail = extract_job_detail(detail_html)
        actions.append(_action(
            trace_id=trace_id,
            step=3,
            action_name="click_job",
            page_url=jobs[0].job_url,
            page_title=detail.page_title or detail.title,
            dom_snapshot=detail_html,
            extraction_result={"job_detail": detail.model_dump()},
            stop_reason=detail_guard.stop_reason or StopReason.SAFE_STOP,
            status=AgentActionStatus.BLOCKED if not detail_guard.allowed else AgentActionStatus.SUCCESS,
            error_message=None if detail_guard.allowed else detail_guard.message,
        ))
    _write_outputs(output_dir, actions, jobs, steps)
    return {
        "trace_id": trace_id,
        "jobs_extracted_count": len(jobs),
        "apply_flow_steps_count": len(steps),
        "blocked_by_login": stop_reason == StopReason.LOGIN_REQUIRED,
        "safe_stop_rate": 1.0,
        "extraction_schema_pass_rate": 1.0,
        "output_dir": str(output_dir),
    }


def _action(
    *,
    trace_id: str,
    step: int,
    action_name: str,
    page_url: str,
    page_title: str,
    dom_snapshot: str,
    extraction_result: dict[str, Any],
    stop_reason: StopReason | None,
    status: AgentActionStatus = AgentActionStatus.SUCCESS,
    error_message: str | None = None,
) -> dict[str, Any]:
    return AgentAction(
        action_type=AgentActionType.TOOL_CALL,
        step_id=f"{trace_id}:{step}",
        trace_id=trace_id,
        action_name=action_name,
        tool_name="recruiting_browser",
        arguments={"action": action_name, "page_url": page_url},
        status=status,
        error_message=error_message,
        timestamp=datetime.now(),
        page_url=page_url,
        page_title=page_title,
        dom_snapshot=truncate_dom_snapshot(dom_snapshot),
        extraction_result=extraction_result,
        stop_reason=stop_reason,
    ).model_dump(mode="json")


def _write_outputs(
    output_dir: Path,
    actions: list[dict[str, Any]],
    jobs: list[JobPosting],
    apply_steps: list[ApplyStep],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "traces.jsonl", actions)
    _write_jsonl(output_dir / "extracted_jobs.jsonl", [job.model_dump() for job in jobs])
    _write_jsonl(output_dir / "apply_flow_steps.jsonl", [step.model_dump() for step in apply_steps])


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _stop_reason_distribution(actions: list[dict[str, Any]]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for action in actions:
        reason = action.get("stop_reason")
        if reason:
            distribution[reason] = distribution.get(reason, 0) + 1
    return distribution


def _safe_stop_rate(actions: list[dict[str, Any]]) -> float:
    stop_reasons = [action.get("stop_reason") for action in actions if action.get("stop_reason")]
    if not stop_reasons:
        return 0.0
    safe_reasons = {
        StopReason.LOGIN_REQUIRED.value,
        StopReason.CAPTCHA_BLOCKED.value,
        StopReason.SAFE_STOP.value,
        StopReason.TASK_COMPLETED.value,
    }
    return sum(1 for reason in stop_reasons if reason in safe_reasons) / len(stop_reasons)


def _fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "LightClaw-safe-dry-run/0.1"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8", errors="replace")
