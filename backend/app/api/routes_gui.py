"""
GUI Agent 单步决策 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.runtime.gui_agent_loop import decide_gui_action, log_gui_trace
from app.schemas.gui_agent import AgentDecision, GuiDecisionRequest, GuiTraceRequest

router = APIRouter(prefix="/v1/gui", tags=["gui"])


@router.post("/decision", response_model=AgentDecision)
async def gui_decision(request: GuiDecisionRequest) -> AgentDecision:
    try:
        return await decide_gui_action(request)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        lowered = message.lower()
        if any(marker in lowered for marker in ["invalid_parameter", "image", "payload", "badrequesterror"]):
            raise HTTPException(status_code=400, detail=f"GUI vision request failed: {message}") from exc
        raise HTTPException(status_code=500, detail=f"GUI decision failed: {exc}") from exc


@router.post("/trace")
async def gui_trace(request: GuiTraceRequest) -> dict:
    try:
        log_gui_trace(request)
        return {"success": True}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"GUI trace logging failed: {exc}") from exc
