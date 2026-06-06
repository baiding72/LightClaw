"""Tests for structured memory scope, local source routing, and memory writes."""

from __future__ import annotations

def test_memory_scope_reports_structured_session_signal():
    from core.memory_scope import infer_memory_scope

    decision = infer_memory_scope("这是当前会话的临时偏好，不要长期保存", "save_user_profile")

    assert decision.scope == "session"
    assert decision.persistence == "current_session"
    trace = decision.to_trace()
    assert trace["memory_intent"] in {"write", "none"}
    assert "当前会话" in trace["memory_signals"] or "临时" in trace["memory_signals"]


def test_memory_scope_prefers_session_for_temporary_note():
    from core.memory_scope import infer_memory_scope

    decision = infer_memory_scope("本轮讨论的要点是关于 API 设计的临时笔记", "save_note")

    assert decision.scope == "session"
    assert decision.persistence == "current_session"


def test_memory_scope_marks_like_as_profile_write():
    from core.memory_scope import infer_memory_scope

    decision = infer_memory_scope("我喜欢喝咖啡", "save_user_profile")

    assert decision.scope == "profile"
    assert decision.intent == "write"


def test_source_routing_marks_project_questions_local_first_without_searching_runs():
    from core.source_routing import infer_source_route

    decision = infer_source_route("myClaw 的 gate policy 是怎么做的", "web_search")

    assert decision.route == "local_first"
    assert decision.local_hits == ()
    assert decision.to_trace()["local_source_hits"] == []


def test_note_create_rejects_duplicate_content(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    monkeypatch.setattr(builtins, "NOTES_DIR", tmp_path)

    first = builtins.save_note.invoke({"content": "同一条项目规范", "title": "规范"})
    second = builtins.save_note.invoke({"content": " 同一条项目规范 ", "title": "规范副本"})

    assert "Note saved" in first
    assert "already exists" in second
    assert (tmp_path / "MEMORY.md").exists()
    assert list(tmp_path.glob("*.md")) == [tmp_path / "MEMORY.md"]


def test_project_memory_note_is_file_backed_and_searchable(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    monkeypatch.setattr(builtins, "NOTES_DIR", tmp_path)

    saved = builtins.save_note.invoke({"content": "项目约定：eval trace 统一用 JSON suite", "title": "eval 约定"})
    note_id = saved.split("[", 1)[1].split("]", 1)[0]

    assert not (tmp_path / f"{note_id}.md").exists()
    search_result = builtins.search_notes.invoke({"keyword": "eval trace"})
    assert note_id in search_result
    assert "ranked by lightweight memory retrieval" in search_result
    assert "score:" in search_result
    assert "JSON suite" in builtins.read_note.invoke({"note_id": note_id})
    assert "eval 约定" in (tmp_path / "MEMORY.md").read_text(encoding="utf-8")


def test_profile_update_rejects_empty_and_marks_conflicts(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    profile = tmp_path / "profile.md"
    profile.write_text("- 回答风格: 简洁\n", encoding="utf-8")
    monkeypatch.setattr(builtins, "PROFILE_FILE", profile)

    empty = builtins.save_user_profile.invoke({"new_content": "   "})
    updated = builtins.save_user_profile.invoke({"new_content": "- 回答风格: 详细"})

    assert "cannot be empty" in empty
    assert "updated" in updated
    assert "conflict notice" in profile.read_text(encoding="utf-8")


def test_profile_update_remove_mode_removes_matching_lines(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    profile = tmp_path / "profile.md"
    profile.write_text("answer_preference: concise\ntemp_language_pref: English only\n", encoding="utf-8")
    monkeypatch.setattr(builtins, "PROFILE_FILE", profile)

    result = builtins.save_user_profile.invoke({"action": "remove", "new_content": "temp_language_pref"})

    assert "updated" in result
    assert "temp_language_pref" not in profile.read_text(encoding="utf-8")


def test_personal_memory_profile_writes_single_profile_file(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    profile = tmp_path / "profile.md"
    monkeypatch.setattr(builtins, "PROFILE_FILE", profile)

    result = builtins.save_user_profile.invoke({"new_content": "- 回答风格: 简洁"})

    assert "User profile saved" in result
    assert not (tmp_path / "memory").exists()
    assert "回答风格" in builtins.read_user_profile.invoke({})


def test_profile_write_normalizes_flat_json_and_rejects_nested_json(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    profile = tmp_path / "profile.md"
    monkeypatch.setattr(builtins, "PROFILE_FILE", profile)

    saved = builtins.save_user_profile.invoke({"new_content": '{"coffee_preference": "茶"}'})
    nested = builtins.save_user_profile.invoke({"new_content": '{"prefs": {"coffee": "茶"}}'})

    content = profile.read_text(encoding="utf-8")
    assert "User profile saved" in saved
    assert "- coffee_preference: 茶" in content
    assert '{"coffee_preference"' not in content
    assert "must be flat" in nested


def test_profile_write_normalizes_remember_wrapped_json(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    profile = tmp_path / "profile.md"
    monkeypatch.setattr(builtins, "PROFILE_FILE", profile)

    saved = builtins.save_user_profile.invoke({"new_content": '- 用户偏好: 请记住：{"answer_style":"concise"}'})

    content = profile.read_text(encoding="utf-8")
    assert "User profile saved" in saved
    assert "- answer_style: concise" in content
    assert '{"answer_style"' not in content
    assert "请记住" not in content


def test_implicit_memory_candidate_counts_session_evidence():
    from core.memory_candidates import extract_memory_candidate_signals

    history = [
        {"role": "user", "content": "这个回答短一点"},
        {"role": "assistant", "content": "好的"},
        {"role": "user", "content": "还是简洁一点"},
    ]

    signals = extract_memory_candidate_signals("这次也短一点，直接说结论", history)

    concise = [signal for signal in signals if signal.key == "answer_style.concise"][0]
    assert concise.evidence_count == 3
    assert concise.would_prompt_for_confirmation is True
    assert concise.persisted is False


def test_implicit_memory_candidate_suppresses_transient_scope():
    from core.memory_candidates import extract_memory_candidate_signals

    signals = extract_memory_candidate_signals("本轮临时用中文回答")

    assert signals
    assert signals[0].suppressed is True
    assert signals[0].suppression_reason == "transient_scope"
    assert signals[0].would_prompt_for_confirmation is False
