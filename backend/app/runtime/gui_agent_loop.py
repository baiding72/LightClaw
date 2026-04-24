"""
GUI Agent 任务主循环
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logger import logger
from app.llm import ChatMessage, BaseLLMAdapter, get_llm_adapter
from app.schemas.gui_agent import (
    ActionExecutionResult,
    AgentDecision,
    AgentLoopResult,
    GuiDecisionRequest,
    GuiTraceRequest,
    Observation,
    ReadTaskExtraction,
)


DPO_SYSTEM_PROMPT = "你是一个集成在浏览器插件中的个人效率 Agent，必须严格依据当前页面的结构化观察结果做出稳定、可执行、可验证的 GUI 决策。"


class ObservationProvider(Protocol):
    async def get_observation(self) -> Observation: ...


class ActionExecutor(Protocol):
    async def execute_action(self, decision: AgentDecision) -> ActionExecutionResult: ...


@dataclass
class GUILoopLogger:
    task_id: str
    output_dir: Path

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = self.output_dir / f"trajectory_gui_{self.task_id}_{timestamp}.jsonl"

    def log(self, event_type: str, payload: dict) -> None:
        event = {
            "event_type": event_type,
            "task_id": self.task_id,
            "timestamp": datetime.now().isoformat(),
            **payload,
        }
        with self.filepath.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")


def _append_jsonl_atomic(filepath: Path, payload: dict) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    fd = os.open(filepath, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def _build_dpo_prompt(task_description: str | None, observation: Observation | None) -> str:
    description = task_description or ""
    if observation is None:
        return description

    return (
        f"任务描述:\n{description}\n\n"
        f"页面元数据:\n{observation.metadata.model_dump_json(indent=2, ensure_ascii=False)}\n\n"
        f"页面可交互元素:\n{observation.som_text[:12000]}\n"
    )


def _write_dpo_preference_pair(request: GuiTraceRequest) -> None:
    if (
        not request.rejected_decision
        or not request.decision
        or not request.execution_result
        or not request.execution_result.success
        or not request.previous_error_trace
    ):
        return

    settings = get_settings()
    dpo_path = Path(settings.data_dir) / "dpo_dataset.jsonl"
    sample = {
        "system": DPO_SYSTEM_PROMPT,
        "prompt": _build_dpo_prompt(request.task_description, request.observation),
        "chosen": json.dumps(request.decision.model_dump(mode="json"), ensure_ascii=False),
        "rejected": json.dumps(request.rejected_decision.model_dump(mode="json"), ensure_ascii=False),
    }
    try:
        _append_jsonl_atomic(dpo_path, sample)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to append DPO sample: %s: %s", type(exc).__name__, exc)


def _extract_json_object(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return stripped
    return stripped[start:end + 1]


def _build_decision_prompt(task_description: str, observation: Observation) -> str:
    return (
        "你是一个严格遵守 schema 的 GUI Agent。\n"
        "你只能基于当前页面可交互元素做决策，不要臆造页面上不存在的元素。\n"
        "你现在可以同时看到网页的 DOM 文本摘要（som_text）和对应的实时截图。\n"
        "截图上用红色框和数字标记的元素，与 som_text 中的 [ID: ...] 严格一一对应。\n"
        "做判断时必须同时结合截图中的视觉排版、卡片边界、空间临近关系，以及 som_text 中的精确 ID；不要只按纯文本顺序盲猜。\n"
        "页面摘要中除了 [ID: ...] 的交互元素外，还可能包含 [TEXT] 开头的静态文本，这些静态文本同样可以作为识别岗位名称、状态、时间等信息的证据。\n"
        "输出必须是单个 JSON 对象，字段只允许："
        'thought_process, action_type, target_id, action_value。\n'
        "动作集合仅允许：CLICK, TYPE, SCROLL, WAIT, FINISH。\n"
        "如果上一步报错，必须利用 previous_error_trace 做自纠错，避免重复同样错误。\n\n"
        "如果 previous_error_trace 提示“滚动后页面没有变化”或“无新增信息”，禁止继续重复相同方向的 SCROLL，必须改为：\n"
        "1. 直接利用当前 [TEXT] 与已知元素完成提取；或\n"
        "2. 点击更可能展开详情/切换视图的元素；或\n"
        "3. 在证据不足时 FINISH 并明确说明缺失字段。\n\n"
        f"任务目标:\n{task_description}\n\n"
        f"页面元数据:\n{observation.metadata.model_dump_json(indent=2, ensure_ascii=False)}\n\n"
        f"页面可交互元素摘要:\n{observation.som_text[:12000]}\n\n"
        f"previous_error_trace:\n{observation.previous_error_trace or 'None'}\n"
    )


def _infer_task_strategy(task_description: str) -> str:
    lowered = task_description.lower()
    write_keywords = ["点击", "输入", "填写", "保存", "选择", "编辑", "下一步", "提交", "click", "type", "fill"]
    read_keywords = ["识别", "提取", "总结", "查看", "检索", "状态", "时间", "记录", "确认", "结果", "summarize", "extract", "read"]

    if any(keyword in lowered for keyword in write_keywords):
      return "write"
    if any(keyword in lowered for keyword in read_keywords):
      return "read"
    return "write"


def _build_read_prompt(task_description: str, observation: Observation) -> str:
    return (
        "你是一个结构化信息提取 Agent，负责把页面里的真实文本精准拆成 JSON 字段。\n"
        "你现在可以同时看到网页的 DOM 文本摘要（som_text）和对应的实时截图。\n"
        "截图上用红色框和数字标记的元素，与 som_text 中的 [ID: ...] 严格一一对应。\n"
        "在提取结构化字段（如招聘岗位、状态、时间）时，必须结合截图中的视觉排版、卡片边界和空间临近关系，来判断静态文本归属于哪条记录。不要仅凭纯文本顺序进行盲猜。\n"
        "绝对禁止脑补，绝对禁止偷懒。不要在 thought_process 里说“已经找到”，却在 JSON 里把字段填成 null。\n"
        "页面摘要中除了 [ID: ...] 的交互元素外，还可能包含 [TEXT] 开头的静态文本，它们同样是有效证据，而且通常比交互元素更重要。\n"
        "你必须优先逐条读取 [TEXT] 内容，并把岗位名、投递时间、状态等信息一字不差地映射到 JSON 字段中。\n"
        "例如，如果看到：[TEXT] 大模型算法实习生 实习 投递时间：2026/04/10 简历筛选中\n"
        "那么必须拆成：job_name='大模型算法实习生'，delivery_time='2026/04/10'，status='简历筛选中'。\n"
        "仅当现有内容明显不足，并且存在合理的下一步交互时，才允许建议 CLICK/SCROLL/WAIT。\n"
        "首屏数据通常是不完整的。除非页面明确显示“没有更多记录”、已经滚动到底部，或 previous_error_trace 明确提示无法继续滚动，否则在提取完当前视口的有效记录后，应优先继续向下 SCROLL，而不是直接 FINISH。\n"
        "如果 previous_error_trace 提示滚动后没有新内容，严禁再次滚动，必须从现有内容提取，或直接结束并说明缺失字段。\n"
        "为了避免 JSON 被截断，输出必须极度精简：thought_process 不超过 40 个汉字；不要输出多余解释。\n"
        "输出必须是单个 JSON 对象，字段只允许："
        "thought_process, records, missing_fields, needs_more_context, suggested_next_action, target_id, action_value。\n"
        "不要输出 summary。\n\n"
        f"任务目标:\n{task_description}\n\n"
        f"页面元数据:\n{observation.metadata.model_dump_json(indent=2, ensure_ascii=False)}\n\n"
        f"页面摘要:\n{observation.som_text[:16000]}\n\n"
        f"previous_error_trace:\n{observation.previous_error_trace or 'None'}\n"
    )


def _build_multimodal_user_content(prompt: str, observation: Observation) -> str | list[dict[str, Any]]:
    screenshot_base64 = (observation.screenshot_base64 or "").strip()
    if not screenshot_base64:
        return prompt

    if screenshot_base64.startswith("data:image"):
        image_url = screenshot_base64
    else:
        image_url = f"data:image/jpeg;base64,{screenshot_base64}"

    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]


async def _infer_read_extraction(
    llm: BaseLLMAdapter,
    task_description: str,
    observation: Observation,
) -> ReadTaskExtraction:
    prompt = _build_read_prompt(task_description, observation)
    try:
        response = await llm.chat(
            [
                ChatMessage(role="system", content="你是一个精确的页面信息提取代理。只输出 JSON。"),
                ChatMessage(role="user", content=_build_multimodal_user_content(prompt, observation)),
            ],
            temperature=0.1,
            max_tokens=420,
        )
    except Exception as exc:
        error_text = str(exc)
        if observation.screenshot_base64 and any(
            marker in error_text.lower()
            for marker in ["invalid_parameter", "image", "payload", "too large", "badrequesterror"]
        ):
            logger.warning("Vision request rejected, falling back to text-only read extraction: %s", error_text)
            fallback_observation = observation.model_copy(deep=True)
            fallback_observation.screenshot_base64 = None
            response = await llm.chat(
                [
                    ChatMessage(role="system", content="你是一个精确的页面信息提取代理。只输出 JSON。"),
                    ChatMessage(role="user", content=_build_read_prompt(task_description, fallback_observation)),
                ],
                temperature=0.1,
                max_tokens=420,
            )
        else:
            raise
    return ReadTaskExtraction.model_validate_json(_extract_json_object(response.content))


def _convert_read_extraction_to_decision(extraction: ReadTaskExtraction) -> AgentDecision:
    action_type = extraction.suggested_next_action or ("SCROLL" if extraction.needs_more_context else "FINISH")
    action_value = extraction.action_value

    if action_type == "FINISH" and not action_value:
        if extraction.records:
            valid_count = sum(1 for record in extraction.records if record.job_name or record.status or record.delivery_time)
            action_value = f"已提取 {valid_count} 条记录"
        else:
            action_value = "提取完成"

    summary = ""
    if extraction.records:
        pieces = []
        for record in extraction.records[:5]:
            fields = [field for field in [record.job_name, record.status, record.delivery_time] if field]
            if fields:
                pieces.append(" / ".join(fields))
        summary = "；".join(pieces)

    return AgentDecision(
        thought_process=extraction.thought_process,
        action_type=action_type,
        target_id=extraction.target_id,
        action_value=action_value,
        strategy="read",
        structured_output={
            "summary": summary,
            "records": [record.model_dump(mode="json") for record in extraction.records],
            "missing_fields": extraction.missing_fields,
            "needs_more_context": extraction.needs_more_context,
        },
    )


async def _infer_decision(
    llm: BaseLLMAdapter,
    task_description: str,
    observation: Observation,
) -> AgentDecision:
    prompt = _build_decision_prompt(task_description, observation)
    try:
        response = await llm.chat(
            [
                ChatMessage(role="system", content="你是一个精确的 GUI 控制代理。只输出 JSON。"),
                ChatMessage(role="user", content=_build_multimodal_user_content(prompt, observation)),
            ],
            temperature=0.1,
            max_tokens=512,
        )
    except Exception as exc:
        error_text = str(exc)
        if observation.screenshot_base64 and any(
            marker in error_text.lower()
            for marker in ["invalid_parameter", "image", "payload", "too large", "badrequesterror"]
        ):
            logger.warning("Vision request rejected, falling back to text-only GUI decision: %s", error_text)
            fallback_observation = observation.model_copy(deep=True)
            fallback_observation.screenshot_base64 = None
            response = await llm.chat(
                [
                    ChatMessage(role="system", content="你是一个精确的 GUI 控制代理。只输出 JSON。"),
                    ChatMessage(role="user", content=_build_decision_prompt(task_description, fallback_observation)),
                ],
                temperature=0.1,
                max_tokens=512,
            )
        else:
            raise
    return AgentDecision.model_validate_json(_extract_json_object(response.content))


async def decide_gui_action(
    request: GuiDecisionRequest,
    *,
    llm: BaseLLMAdapter | None = None,
) -> AgentDecision:
    runtime_llm = llm or get_llm_adapter()
    task_id = request.task_id or f"gui_decision_{uuid.uuid4().hex[:8]}"
    logger = GUILoopLogger(task_id, Path(get_settings().trajectories_dir))

    observation = request.observation.model_copy(deep=True)
    observation.previous_error_trace = request.previous_error_trace

    logger.log(
        "observation",
        {
            "step_index": request.step_index or 1,
            "observation": observation.model_dump(mode="json"),
        },
    )
    strategy = _infer_task_strategy(request.task_description)

    last_error: Exception | None = None
    for retry_index in range(3):
        try:
            if strategy == "read":
                extraction = await _infer_read_extraction(runtime_llm, request.task_description, observation)
                decision = _convert_read_extraction_to_decision(extraction)
            else:
                decision = await _infer_decision(runtime_llm, request.task_description, observation)
                decision.strategy = "write"

            logger.log(
                "decision",
                {
                    "step_index": request.step_index or 1,
                    "retry_index": retry_index,
                    "strategy": strategy,
                    "decision": decision.model_dump(mode="json"),
                },
            )
            return decision
        except ValidationError as exc:
            last_error = exc
            observation.previous_error_trace = str(exc)
            logger.log(
                "decision_validation_error",
                {
                    "step_index": request.step_index or 1,
                    "retry_index": retry_index,
                    "strategy": strategy,
                    "error": str(exc),
                },
            )
            continue

    assert last_error is not None
    raise last_error


def log_gui_trace(request: GuiTraceRequest) -> None:
    logger = GUILoopLogger(request.task_id, Path(get_settings().trajectories_dir))

    if request.observation:
        logger.log(
            "frontend_observation",
            {
                "step_index": request.step_index,
                "task_description": request.task_description,
                "observation": request.observation.model_dump(mode="json"),
            },
        )

    if request.decision:
        logger.log(
            "frontend_decision",
            {
                "step_index": request.step_index,
                "decision": request.decision.model_dump(mode="json"),
                "previous_error_trace": request.previous_error_trace,
            },
        )

    if request.execution_result:
        logger.log(
            "frontend_execution_result",
            {
                "step_index": request.step_index,
                "execution_result": request.execution_result.model_dump(mode="json"),
            },
        )

    if (
        request.rejected_decision
        and request.decision
        and request.execution_result
        and request.execution_result.success
        and request.previous_error_trace
    ):
        logger.log(
            "preference_pair",
            {
                "step_index": request.step_index,
                "trajectory_type": "repair_preference_pair",
                "rejected": {
                    "decision": request.rejected_decision.model_dump(mode="json"),
                    "error_trace": request.previous_error_trace,
                },
                "chosen": {
                    "decision": request.decision.model_dump(mode="json"),
                    "execution_result": request.execution_result.model_dump(mode="json"),
                },
            },
        )
        _write_dpo_preference_pair(request)


async def run_agent_loop(
    task_description: str,
    observation_provider: ObservationProvider,
    action_executor: ActionExecutor,
    *,
    llm: BaseLLMAdapter | None = None,
    max_steps: int = 15,
    max_retries: int = 3,
    task_id: str | None = None,
) -> AgentLoopResult:
    """
    GUI Agent 执行闭环

    采用 Observe -> Predict -> Act -> Verify，并在决策校验失败或动作失败时进行自纠错。
    """
    runtime_llm = llm or get_llm_adapter()
    run_id = task_id or f"gui_{uuid.uuid4().hex[:8]}"
    logger = GUILoopLogger(run_id, Path(get_settings().trajectories_dir))
    retry_count = 0
    last_decision: AgentDecision | None = None
    last_execution_result: ActionExecutionResult | None = None
    previous_error_trace: str | None = None

    for step_index in range(1, max_steps + 1):
        observation = await observation_provider.get_observation()
        observation.previous_error_trace = previous_error_trace
        logger.log(
            "observation",
            {
                "step_index": step_index,
                "observation": observation.model_dump(mode="json"),
            },
        )

        retry_in_step = 0
        while retry_in_step < max_retries:
            try:
                decision = await _infer_decision(runtime_llm, task_description, observation)
                last_decision = decision
                logger.log(
                    "decision",
                    {
                        "step_index": step_index,
                        "retry_index": retry_in_step,
                        "decision": decision.model_dump(mode="json"),
                    },
                )
            except ValidationError as exc:
                retry_count += 1
                retry_in_step += 1
                previous_error_trace = f"Decision schema validation failed: {exc}"
                logger.log(
                    "decision_validation_error",
                    {
                        "step_index": step_index,
                        "retry_index": retry_in_step,
                        "error": previous_error_trace,
                    },
                )
                observation.previous_error_trace = previous_error_trace
                continue
            except Exception as exc:  # noqa: BLE001
                retry_count += 1
                retry_in_step += 1
                previous_error_trace = f"Decision inference failed: {type(exc).__name__}: {exc}"
                logger.log(
                    "decision_runtime_error",
                    {
                        "step_index": step_index,
                        "retry_index": retry_in_step,
                        "error": previous_error_trace,
                    },
                )
                observation.previous_error_trace = previous_error_trace
                continue

            if decision.action_type == "FINISH":
                summary = decision.action_value or decision.thought_process
                logger.log(
                    "finish",
                    {
                        "step_index": step_index,
                        "summary": summary,
                    },
                )
                return AgentLoopResult(
                    success=True,
                    summary=summary,
                    total_steps=step_index,
                    retry_count=retry_count,
                    final_observation=observation,
                    last_decision=decision,
                    last_execution_result=last_execution_result,
                )

            execution_result = await action_executor.execute_action(decision)
            last_execution_result = execution_result
            logger.log(
                "execution_result",
                {
                    "step_index": step_index,
                    "retry_index": retry_in_step,
                    "execution_result": execution_result.model_dump(mode="json"),
                },
            )

            if execution_result.success:
                previous_error_trace = None
                break

            retry_count += 1
            retry_in_step += 1
            previous_error_trace = (
                f"Action {execution_result.action_type} failed with "
                f"{execution_result.status}: {execution_result.error or execution_result.detail or 'unknown error'}"
            )
            observation.previous_error_trace = previous_error_trace

        else:
            summary = f"动作执行连续失败，已超过最大重试次数。请用户接管。最后错误：{previous_error_trace or 'unknown'}"
            logger.log(
                "handoff_required",
                {
                    "step_index": step_index,
                    "error": previous_error_trace,
                },
            )
            return AgentLoopResult(
                success=False,
                summary=summary,
                total_steps=step_index,
                retry_count=retry_count,
                final_observation=observation,
                last_decision=last_decision,
                last_execution_result=last_execution_result,
            )

    summary = "达到最大步骤限制，任务未完成。"
    logger.log(
        "max_steps_exceeded",
        {
            "total_steps": max_steps,
            "retry_count": retry_count,
        },
    )
    return AgentLoopResult(
        success=False,
        summary=summary,
        total_steps=max_steps,
        retry_count=retry_count,
        final_observation=observation,
        last_decision=last_decision,
        last_execution_result=last_execution_result,
    )
