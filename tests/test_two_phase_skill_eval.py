from evals.two_phase_skills import SCENARIOS, run_scenario
from core.logger import RunLogger


def test_two_phase_skill_eval_scenario_passes(tmp_path):
    logger = RunLogger(run_id="two-phase-test", runs_dir=tmp_path)

    passed, failures = run_scenario(SCENARIOS[0], logger)

    assert passed
    assert failures == []
    assert logger.path.exists()
    assert "eval_case_completed" in logger.path.read_text(encoding="utf-8")
