"""
LLM 配置相关 Schema
"""
from typing import Optional

from pydantic import BaseModel, Field


class LLMProfileUpsert(BaseModel):
    profile_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=1, max_length=300)
    api_key: str = Field(default="", max_length=300)


class LLMProfileResponse(BaseModel):
    profile_id: str
    name: str
    provider: str
    model: str
    base_url: str
    has_api_key: bool
    api_key_masked: str


class LLMSettingsResponse(BaseModel):
    active_profile_id: Optional[str] = None
    profiles: list[LLMProfileResponse]


class LLMActivateRequest(BaseModel):
    profile_id: str
