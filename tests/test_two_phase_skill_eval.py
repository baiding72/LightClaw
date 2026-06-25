from evals.two_phase_skills import SCENARIOS, run_scenario
from core.logger import RunLogger


def test_two_phase_skill_eval_migrates_all_cyberclaw_scenarios():
    case_ids = {scenario.case_id for scenario in SCENARIOS}

    assert len(SCENARIOS) == 20
    assert "community_ban_permission" in case_ids
    assert "payment_gateway_restart" in case_ids
    assert "docker_image_build" in case_ids
    assert "db_root_password_reset" in case_ids


def test_two_phase_skill_eval_scenario_passes(tmp_path):
    logger = RunLogger(run_id="two-phase-test", runs_dir=tmp_path)

    passed, failures = run_scenario(SCENARIOS[0], logger)

    assert passed
    assert failures == []
    assert logger.path.exists()
    assert "eval_case_completed" in logger.path.read_text(encoding="utf-8")
