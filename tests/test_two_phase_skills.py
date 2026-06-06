"""CyberClaw two-phase skill experiment migrated to myClaw.

The original CyberClaw script uses a live model to compare "single-stage run"
against "help -> run". This migrated pytest keeps the same evaluation idea but
uses a deterministic queued model, so the test is stable and does not require an
API key.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AIMessage

from core.agent import create_agent_harness
from core.policy import ToolPolicy
from core.tools.base import FunctionTool
from tests.test_mvp_learning import QueueChatModel


@dataclass(frozen=True)
class TwoPhaseScenario:
    query: str
    trap_name: str
    trap_brief: str
    trap_manual: str
    correct_name: str
    correct_brief: str
    correct_manual: str


SCENARIOS = [
    TwoPhaseScenario(
        query="用户订单 X112233 申请退款，立刻处理",
        trap_name="finance_billing_and_refund",
        trap_brief="财务资金流水与退款操作中心。",
        trap_manual="仅用于 B2B 供应商大额结算退回，严禁用于 C 端订单。",
        correct_name="order_aftersales_processor",
        correct_brief="交易订单履约与售后系统。",
        correct_manual="用于处理 C 端常规用户的订单退款及物流拦截。",
    ),
    TwoPhaseScenario(
        query="重启一下用户中心的 Redis 缓存实例",
        trap_name="database_cache_refresher",
        trap_brief="数据库缓存刷新与重启控制台。",
        trap_manual="仅支持 MySQL/PG 查询缓存刷新，不能处理 Redis。",
        correct_name="nosql_memory_orchestrator",
        correct_brief="KV 内存数据库调度中心。",
        correct_manual="专门负责 Redis 和 Memcached 等内存实例的监控与平滑重启。",
    ),
    TwoPhaseScenario(
        query="把线上的前端商城回滚到上一个版本",
        trap_name="online_code_rollback_tool",
        trap_brief="线上代码版本回滚工具。",
        trap_manual="只做 git reset，不负责生产静态资源发布。",
        correct_name="cdn_static_pipeline",
        correct_brief="CDN 资源与前端发布流水线。",
        correct_manual="支持将 CDN 静态前端资源切换到上一个稳定版本。",
    ),
    TwoPhaseScenario(
        query="给新来的实习生开通 VPN 权限",
        trap_name="employee_permission_granter",
        trap_brief="企业员工权限开通管理台。",
        trap_manual="只分配 Jira/Gitlab/Wiki 权限，不能处理网络 VPN。",
        correct_name="zero_trust_network_admin",
        correct_brief="零信任网络与接入网关。",
        correct_manual="用于管理 VPN 账号开通及办公网接入授权。",
    ),
    TwoPhaseScenario(
        query="清理系统盘里的 /tmp 过期临时文件",
        trap_name="disk_space_releaser",
        trap_brief="磁盘空间深度释放与清空工具。",
        trap_manual="毁灭性工具，用于退役前彻底抹除整盘数据。",
        correct_name="tmp_fragment_sweeper",
        correct_brief="系统临时碎片安全清扫机。",
        correct_manual="安全识别并清理系统盘内 /tmp 过期临时文件。",
    ),
]


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

