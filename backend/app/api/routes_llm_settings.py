"""
LLM 配置 API
"""
from fastapi import APIRouter, HTTPException

from app.schemas.llm_settings import (
    LLMActivateRequest,
    LLMProfileUpsert,
    LLMSettingsResponse,
)
from app.services.llm_settings_service import LLMSettingsService

router = APIRouter(prefix="/settings/llm", tags=["llm-settings"])


@router.get("", response_model=LLMSettingsResponse)
async def get_llm_settings() -> LLMSettingsResponse:
    service = LLMSettingsService()
    return service.get_settings_payload()


@router.post("/profiles", response_model=LLMSettingsResponse)
async def upsert_llm_profile(payload: LLMProfileUpsert) -> LLMSettingsResponse:
    service = LLMSettingsService()
    return await service.upsert_profile(payload)


@router.post("/activate", response_model=LLMSettingsResponse)
async def activate_llm_profile(payload: LLMActivateRequest) -> LLMSettingsResponse:
    service = LLMSettingsService()
    try:
        return await service.activate_profile(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
