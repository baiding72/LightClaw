from evals.memory_policy_cases import DEFAULT_SUITE, load_json, load_trace_cases, run_trace_suite


def test_memory_policy_badcases_load_from_json():
    suite = load_json(DEFAULT_SUITE)
    cases = load_trace_cases(suite)

    assert suite["suite_id"] == "memory_policy_badcases"
    assert len(cases) == 7
    assert cases[0].checker_id == "scope_consistency"


def test_memory_policy_trace_suite_reports_selected_case(tmp_path, monkeypatch):
    suite = {
        "suite_id": "memory_policy_test",
        "title": "Memory policy smoke",
        "runner": "trace_regression",
        "cases": [
            {
                "case_id": "missing_trace_case",
                "title": "missing trace is reported",
                "trace_paths": ["missing-trace.jsonl"],
                "checker": "source_routing",
            }
        ],
    }
    monkeypatch.setattr("evals.memory_policy_cases.RUNS_DIR", tmp_path)

    exit_code = run_trace_suite(suite, suite_path=tmp_path / "suite.json")

    assert exit_code == 1
