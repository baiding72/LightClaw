"""Tests for tool permission policy primitives."""

from core.policy import ToolGateContext, ToolGateDecision, ToolPolicy
from core.agent import create_agent_harness
from core.state import AgentState
from tests.test_mvp_learning import QueueChatModel
from langchain_core.messages import AIMessage


def test_off_policy_allows_without_monitoring_side_effects():
    policy = ToolPolicy(mode="off")

    result = policy.evaluate(ToolGateContext(tool_name="save_user_profile", args={"new_content": "x"}))

    assert result.decision == ToolGateDecision.ALLOW
    assert result.mode == "off"
    assert "关闭" in result.reason


def test_monitor_alias_records_sensitive_tool_as_auto_ask():
    policy = ToolPolicy(mode="monitor")

    result = policy.evaluate(ToolGateContext(tool_name="save_user_profile", args={"new_content": "x"}))

    assert result.decision == ToolGateDecision.ASK
    assert result.permission.key == "memory.profile:write"
    assert result.permission.requires_consent is True
    assert result.mode == "auto"


def test_enforce_policy_asks_for_sensitive_tool_without_grant():
    policy = ToolPolicy(mode="enforce")

    result = policy.evaluate(ToolGateContext(tool_name="web_search", args={"query": "myClaw"}))

    assert result.decision == ToolGateDecision.ASK
    assert result.permission.key == "external.web:search"
    assert result.mode == "default"
    assert result.metadata["source_route"] in {"local_first", "unclear", "network_candidate"}


def test_enforce_policy_allows_sensitive_tool_with_grant():
    policy = ToolPolicy(mode="enforce")

    result = policy.evaluate(
        ToolGateContext(
            tool_name="save_note",
            args={"action": "edit", "note_id": "abc", "content": "x", "_permission_grant": "allow"},
        )
    )

    assert result.decision == ToolGateDecision.ALLOW
    assert result.permission.key == "memory.note:write"


def test_monitor_policy_denies_session_scope_profile_write_even_with_grant():
    policy = ToolPolicy(mode="monitor")

    result = policy.evaluate(
        ToolGateContext(
            tool_name="save_user_profile",
            args={"new_content": "temp", "_permission_grant": "allow"},
            user_input="我的临时偏好是所有回答都用英文",
        )
    )

    assert result.decision == ToolGateDecision.DENY
    assert result.metadata["memory_scope"] == "session"


def test_monitor_policy_denies_session_scope_note_write():
    policy = ToolPolicy(mode="monitor")

    result = policy.evaluate(
        ToolGateContext(
            tool_name="save_note",
            args={"content": "API 设计临时笔记", "_permission_grant": "allow"},
            user_input="本轮讨论的要点是关于 API 设计的临时笔记",
        )
    )

    assert result.decision == ToolGateDecision.DENY
    assert result.metadata["memory_scope"] == "session"


def test_policy_denies_sensitive_memory_even_when_off():
    policy = ToolPolicy(mode="off")

    result = policy.evaluate(
        ToolGateContext(
            tool_name="save_user_profile",
            args={"new_content": "银行卡密码：abc123"},
            user_input="把用户的银行卡密码记住：abc123",
        )
    )

    assert result.decision == ToolGateDecision.DENY
    assert result.metadata["sensitive_memory"] is True


def test_default_policy_asks_for_write_tool_by_default():
    policy = ToolPolicy(mode="default")

    result = policy.evaluate(ToolGateContext(tool_name="write_office_file", args={"relative_path": "note.md", "content": "x"}))

    assert result.decision == ToolGateDecision.ASK
    assert result.permission.key == "office.file:create"


def test_plan_policy_allows_reads_and_denies_writes():
    policy = ToolPolicy(mode="plan")

    read_result = policy.evaluate(ToolGateContext(tool_name="read_office_file", args={"relative_path": "note.md"}))
    write_result = policy.evaluate(ToolGateContext(tool_name="write_office_file", args={"relative_path": "note.md", "content": "x"}))

    assert read_result.decision == ToolGateDecision.ALLOW
    assert write_result.decision == ToolGateDecision.DENY
    assert "plan 模式" in write_result.reason


def test_plan_policy_allows_dynamic_skill_help_but_not_run():
    policy = ToolPolicy(mode="plan")

    help_result = policy.evaluate(ToolGateContext(tool_name="metadata-demo", args={"mode": "help"}))
    run_result = policy.evaluate(ToolGateContext(tool_name="metadata-demo", args={"mode": "run", "command": "echo ok"}))

    assert help_result.decision == ToolGateDecision.ALLOW
    assert help_result.permission.key == "tool:execute"
    assert "skill help" in help_result.reason
    assert run_result.decision == ToolGateDecision.ASK
    assert run_result.permission.key == "tool:execute"


def test_auto_policy_allows_read_only_tools():
    policy = ToolPolicy(mode="auto")

    result = policy.evaluate(ToolGateContext(tool_name="read_office_file", args={"relative_path": "note.md"}))

    assert result.decision == ToolGateDecision.ALLOW
    assert "只读" in result.reason


def test_deny_rules_run_before_off_mode_for_dangerous_shell():
    policy = ToolPolicy(mode="off")

    result = policy.evaluate(ToolGateContext(tool_name="execute_office_shell", args={"command": "sudo whoami"}))

    assert result.decision == ToolGateDecision.DENY
    assert "危险" in result.reason


def test_off_policy_does_not_emit_gate_events_in_agent_loop():
    llm = QueueChatModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_1", "name": "echo", "args": {"message": "hi"}}],
            ),
            AIMessage(content="done"),
        ]
    )
    harness = create_agent_harness(llm, tool_policy=ToolPolicy(mode="off"))

    result = harness.run("say hi")

    assert result["tool_gate_events"] == []


def test_agent_memory_commitment_hook_blocks_false_save_claim():
    llm = QueueChatModel([AIMessage(content="已记住，以后我会这样做。")])
    harness = create_agent_harness(llm, tools=[], tool_policy=ToolPolicy(mode="off"))

    result = harness.run("请记住：以后解释 agent harness 时用固定结构")

    assert "没有保存或更新" in result["answer"]
    assert result["hook_events"]


def test_agent_memory_commitment_hook_catches_future_commitment():
    llm = QueueChatModel([AIMessage(content="好的，以后会按这个方式回答。")])
    harness = create_agent_harness(llm, tools=[], tool_policy=ToolPolicy(mode="off"))

    result = harness.run("请记住：以后解释 agent harness 时用固定结构")

    assert "没有保存或更新" in result["answer"]
    assert result["hook_events"][0]["hook"] == "memory_commitment_guard"


def test_agent_memory_commitment_hook_ignores_project_memory_queries():
    llm = QueueChatModel([AIMessage(content="项目约定是 JSON suite。")])
    harness = create_agent_harness(llm, tools=[], tool_policy=ToolPolicy(mode="off"))

    result = harness.run("我们项目里 eval trace 的展示约定是什么？")

    assert result["answer"] == "项目约定是 JSON suite。"
    assert result["hook_events"] == []


def test_agent_sensitive_memory_guard_refuses_without_tool():
    llm = QueueChatModel([AIMessage(content="好的。")])
    harness = create_agent_harness(llm, tools=[], tool_policy=ToolPolicy(mode="off"))

    result = harness.run("把用户的银行卡密码记住：abc123")

    assert "不能保存" in result["answer"]
    assert result["hook_events"][0]["hook"] == "sensitive_memory_refusal_guard"


def test_agent_sensitive_memory_guard_has_priority_over_commitment_words():
    llm = QueueChatModel([AIMessage(content="好的，我会保存这个银行卡密码。")])
    harness = create_agent_harness(llm, tools=[], tool_policy=ToolPolicy(mode="off"))

    result = harness.run("把用户的银行卡密码记住：abc123")

    assert "不能保存" in result["answer"]
    assert result["hook_events"][0]["hook"] == "sensitive_memory_refusal_guard"


def test_agent_auto_writes_clear_profile_preference(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    profile = tmp_path / "profile.md"
    monkeypatch.setattr(builtins, "PROFILE_FILE", profile)
    llm = QueueChatModel([AIMessage(content="已保存你的咖啡偏好。")])
    harness = create_agent_harness(
        llm,
        tools=[builtins.save_user_profile],
        tool_policy=ToolPolicy(mode="off"),
    )

    result = harness.run("我喜欢喝咖啡")

    tool_results = [msg for msg in result["state"].messages if msg.role == "tool"]
    assert tool_results[0].name == "save_user_profile"
    assert "我喜欢喝咖啡" in profile.read_text(encoding="utf-8")
    assert result["hook_events"] == []


def test_agent_auto_writes_explicit_remember_profile_preference(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    profile = tmp_path / "profile.md"
    monkeypatch.setattr(builtins, "PROFILE_FILE", profile)
    llm = QueueChatModel([AIMessage(content="已保存。")])
    harness = create_agent_harness(
        llm,
        tools=[builtins.save_user_profile],
        tool_policy=ToolPolicy(mode="off"),
    )

    result = harness.run("请记住：以后回答我的问题先给结论，再解释原因。")

    tool_results = [msg for msg in result["state"].messages if msg.role == "tool"]
    assert tool_results[0].name == "save_user_profile"
    assert "先给结论" in profile.read_text(encoding="utf-8")


def test_agent_auto_profile_write_skips_memory_queries(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    profile = tmp_path / "profile.md"
    monkeypatch.setattr(builtins, "PROFILE_FILE", profile)
    llm = QueueChatModel([AIMessage(content="我没有可用的已保存记忆。")])
    harness = create_agent_harness(
        llm,
        tools=[builtins.save_user_profile],
        tool_policy=ToolPolicy(mode="off"),
    )

    result = harness.run("我之前告诉过你我的偏好，说说看？")

    assert [msg for msg in result["state"].messages if msg.role == "tool"] == []
    assert not profile.exists()


def test_agent_auto_writes_clear_project_memory(tmp_path, monkeypatch):
    import core.tools.builtins as builtins

    monkeypatch.setattr(builtins, "NOTES_DIR", tmp_path)
    llm = QueueChatModel([AIMessage(content="已保存项目约定。")])
    harness = create_agent_harness(
        llm,
        tools=[builtins.save_note],
        tool_policy=ToolPolicy(mode="off"),
    )

    result = harness.run("把这个项目约定记下来：eval trace 统一用 JSON suite 展示。")

    tool_results = [msg for msg in result["state"].messages if msg.role == "tool"]
    assert tool_results[0].name == "save_note"
    assert "JSON suite" in (tmp_path / "MEMORY.md").read_text(encoding="utf-8")


def test_agent_no_memory_fabrication_guard():
    llm = QueueChatModel([AIMessage(content="我记得你说过喜欢简洁回答。")])
    harness = create_agent_harness(llm, tools=[], tool_policy=ToolPolicy(mode="off"))
    harness._load_memory_context = lambda: ""

    result = harness.run("我之前告诉过你我的偏好，说说看？")

    assert "没有可用的已保存记忆" in result["answer"]
    assert result["hook_events"][0]["hook"] == "no_memory_fabrication_guard"


def test_agent_read_modify_write_guard_blocks_false_note_update():
    harness = create_agent_harness(QueueChatModel([]), tools=[], tool_policy=ToolPolicy(mode="off"))
    state = AgentState()
    state.add_user_message("补充刚才 eval trace 的约定：memory/policy badcase 也必须用同一套 JSON suite。")
    state.add_tool_message("read_note", "# eval 约定\n\n旧内容")

    answer, hooks = harness._apply_completion_hook(
        "补充刚才 eval trace 的约定：memory/policy badcase 也必须用同一套 JSON suite。",
        "已更新这条项目记忆。",
        state,
    )

    assert "没有更新这条项目记忆" in answer
    assert hooks[0]["hook"] == "read_modify_write_guard"
