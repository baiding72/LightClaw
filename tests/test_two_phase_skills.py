"""CyberClaw two-phase skill experiment migrated to myClaw.

The original CyberClaw script uses a live model to compare "single-stage run"
against "help -> run". This migrated pytest keeps the same evaluation idea but
uses a deterministic queued model, so the test is stable and does not require an
API key.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from core.agent import create_agent_harness
from core.policy import ToolPolicy
from core.tools.base import FunctionTool
from evals.two_phase_skills import SCENARIOS, TwoPhaseScenario
from tests.test_mvp_learning import QueueChatModel


def _single_tool(scenario: TwoPhaseScenario, *, trap: bool) -> FunctionTool:
    name = scenario.trap_name if trap else scenario.correct_name
    description = scenario.trap_brief if trap else scenario.correct_brief

    def run(action: str) -> str:
        if trap:
            return f"[FATAL] wrong tool selected. Manual would have warned: {scenario.trap_manual}"
        return f"[SUCCESS] {name}: {action}"

    return FunctionTool(
        run,
        name=name,
        description=description,
        parameters={
            "properties": {"action": {"type": "string", "description": "Action to execute."}},
            "required": ["action"],
        },
    )


def _dual_tool(scenario: TwoPhaseScenario, *, trap: bool) -> FunctionTool:
    name = scenario.trap_name if trap else scenario.correct_name
    description = scenario.trap_brief if trap else scenario.correct_brief
    manual = scenario.trap_manual if trap else scenario.correct_manual

    def run(mode: str, action: str = "") -> str:
        if mode == "help":
            return f"[HELP] {name}: {manual}"
        if mode == "run":
            if trap:
                return f"[FATAL] {name}: help already said this is wrong."
            return f"[SUCCESS] {name}: {action}"
        return "Error: mode must be help or run."

    return FunctionTool(
        run,
        name=name,
        description=description + " First call mode='help'; run only after the manual fits.",
        parameters={
            "properties": {
                "mode": {"type": "string", "description": "help or run"},
                "action": {"type": "string", "description": "Action for run mode."},
            },
            "required": ["mode"],
        },
    )


def _contents(result: dict) -> list[str]:
    return [message.content for message in result["state"].messages if message.role == "tool"]


def test_single_stage_can_step_on_trap_tool():
    scenario = SCENARIOS[0]
    tools = [_single_tool(scenario, trap=True), _single_tool(scenario, trap=False)]
    llm = QueueChatModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "single_trap",
                        "name": scenario.trap_name,
                        "args": {"action": scenario.query},
                    }
                ],
            ),
            AIMessage(content="done"),
        ]
    )
    harness = create_agent_harness(llm, tools=tools, tool_policy=ToolPolicy(mode="off"))

    result = harness.run(scenario.query)

    assert any("[FATAL]" in content for content in _contents(result))


def test_two_stage_help_then_run_avoids_traps_for_all_scenarios():
    successes = 0
    fatals = 0
    help_reads = 0

    for scenario in SCENARIOS:
        tools = [_dual_tool(scenario, trap=True), _dual_tool(scenario, trap=False)]
        llm = QueueChatModel(
            [
                AIMessage(
                    content="",
                    tool_calls=[{"id": "help_trap", "name": scenario.trap_name, "args": {"mode": "help"}}],
                ),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "help_correct", "name": scenario.correct_name, "args": {"mode": "help"}}],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "run_correct",
                            "name": scenario.correct_name,
                            "args": {"mode": "run", "action": scenario.query},
                        }
                    ],
                ),
                AIMessage(content="safe completion"),
            ]
        )
        harness = create_agent_harness(llm, tools=tools, max_turns=6, tool_policy=ToolPolicy(mode="off"))

        result = harness.run(scenario.query)
        contents = _contents(result)
        help_reads += sum(1 for content in contents if "[HELP]" in content)
        successes += int(any("[SUCCESS]" in content for content in contents))
        fatals += int(any("[FATAL]" in content for content in contents))

    assert help_reads == len(SCENARIOS) * 2
    assert successes == len(SCENARIOS)
    assert fatals == 0
