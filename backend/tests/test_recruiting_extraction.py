from pathlib import Path

from app.recruiting import extract_apply_flow, extract_job_list
from app.recruiting.collector import collect_fixture_trajectories
from app.recruiting.eval import calculate_recruiting_metrics
from app.recruiting.guard import RecruitingGuard
from app.schemas.action import StopReason

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "recruiting"


def test_extract_job_list() -> None:
    jobs = extract_job_list((FIXTURE_DIR / "careers_list.html").read_text(encoding="utf-8"))

    assert len(jobs) == 2
    assert jobs[0].job_id == "job_llm_intern"
    assert jobs[0].title == "大语言模型算法实习生"
    assert jobs[0].job_url == "https://fixture.local/jobs/llm-intern"


def test_extract_apply_flow() -> None:
    steps = extract_apply_flow((FIXTURE_DIR / "apply_page.html").read_text(encoding="utf-8"))

    assert [step.step_id for step in steps] == ["name", "email", "motivation", "resume"]
    assert steps[0].required is True
    assert steps[-1].control_type == "file"


def test_recruiting_guard_stops_login_and_upload() -> None:
    html = (FIXTURE_DIR / "apply_page.html").read_text(encoding="utf-8")
    result = RecruitingGuard().inspect_page(html)

    assert result.allowed is False
    assert result.stop_reason == StopReason.LOGIN_REQUIRED

    captcha_html = (FIXTURE_DIR / "apply_captcha_page.html").read_text(encoding="utf-8")
    captcha_result = RecruitingGuard().inspect_page(captcha_html)
    assert captcha_result.allowed is False
    assert captcha_result.stop_reason == StopReason.CAPTCHA_BLOCKED

    upload_html = (FIXTURE_DIR / "apply_upload_page.html").read_text(encoding="utf-8")
    upload_result = RecruitingGuard().inspect_page(upload_html)
    assert upload_result.allowed is False
    assert upload_result.stop_reason == StopReason.SAFE_STOP

    submit_result = RecruitingGuard().validate_action("submit_application", "")
    assert submit_result.allowed is False
    assert submit_result.stop_reason == StopReason.SAFE_STOP


def test_collect_fixture_trajectories_outputs_schema(tmp_path: Path) -> None:
    summary = collect_fixture_trajectories(FIXTURE_DIR, tmp_path)

    assert summary["jobs_extracted_count"] == 2
    assert summary["apply_flow_steps_count"] == 8
    assert summary["blocked_by_login"] is True
    assert summary["blocked_by_captcha"] is True
    assert summary["safe_stop_count"] == 2
    assert summary["safe_stop_rate"] == 1.0
    assert summary["stop_reason_distribution"] == {
        "login_required": 1,
        "captcha_blocked": 1,
        "safe_stop": 2,
    }
    assert (tmp_path / "traces.jsonl").exists()
    assert (tmp_path / "extracted_jobs.jsonl").exists()
    assert (tmp_path / "apply_flow_steps.jsonl").exists()

    metrics = calculate_recruiting_metrics(tmp_path)
    assert metrics["jobs_extracted_count"] == 2
    assert metrics["apply_flow_steps_count"] == 8
    assert metrics["blocked_by_login"] is True
    assert metrics["blocked_by_captcha"] is True
    assert metrics["safe_stop_count"] == 2
    assert metrics["safe_stop_rate"] == 1.0
    assert metrics["stop_reason_distribution"] == {
        "login_required": 1,
        "captcha_blocked": 1,
        "safe_stop": 2,
    }
    assert metrics["extraction_schema_pass_rate"] == 1.0
