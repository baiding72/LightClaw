"""
LLM 配置持久化服务
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.api.routes_health import reset_llm_health_cache
from app.core.config import get_settings, refresh_settings
from app.llm import reset_llm_adapter
from app.schemas.llm_settings import (
    LLMActivateRequest,
    LLMProfileResponse,
    LLMProfileUpsert,
    LLMSettingsResponse,
)


class LLMSettingsService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.file_path = Path(self.settings.data_dir) / "llm_profiles.json"

    def _read_payload(self) -> dict:
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            return {"active_profile_id": None, "profiles": []}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            return {"active_profile_id": None, "profiles": []}

    def _write_payload(self, payload: dict) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _mask_api_key(self, api_key: str) -> str:
        if not api_key:
            return ""
        if len(api_key) <= 8:
            return "*" * len(api_key)
        return f"{api_key[:4]}{'*' * (len(api_key) - 8)}{api_key[-4:]}"

    def _provider_display_name(self, provider: str) -> str:
        normalized = (provider or "").strip().lower()
        if normalized == "deepseek":
            return "DeepSeek"
        if normalized == "qwen":
            return "Qwen"
        if normalized == "openai":
            return "OpenAI"
        return provider or "Custom"

    def _normalize_profile_name(self, profile: dict) -> str:
        current_name = str(profile.get("name", "")).strip()
        provider_name = self._provider_display_name(str(profile.get("provider", "")))
        legacy_names = {"当前配置", "qwen 快速切换", "deepseek 快速切换", "openai 快速切换"}
        if not current_name or current_name.lower() in legacy_names or "快速切换" in current_name:
            return provider_name
        return current_name

    def _normalize_payload(self, payload: dict) -> dict:
        profiles = payload.get("profiles", [])
        changed = False
        normalized_profiles = []
        for profile in profiles:
            updated = dict(profile)
            normalized_name = self._normalize_profile_name(updated)
            if updated.get("name") != normalized_name:
                updated["name"] = normalized_name
                changed = True
            normalized_profiles.append(updated)
        if changed:
            payload["profiles"] = normalized_profiles
        return payload

    def _to_response(self, profile: dict) -> LLMProfileResponse:
        api_key = str(profile.get("api_key", ""))
        return LLMProfileResponse(
            profile_id=str(profile["profile_id"]),
            name=self._normalize_profile_name(profile),
            provider=str(profile["provider"]),
            model=str(profile["model"]),
            base_url=str(profile["base_url"]),
            has_api_key=bool(api_key),
            api_key_masked=self._mask_api_key(api_key),
        )

    def get_settings_payload(self) -> LLMSettingsResponse:
        payload = self._read_payload()
        if not payload.get("profiles"):
            bootstrap_profile = {
                "profile_id": "default",
                "name": self._provider_display_name(self.settings.llm_provider),
                "provider": self.settings.llm_provider,
                "model": self.settings.llm_model,
                "base_url": self.settings.llm_base_url,
                "api_key": self.settings.llm_api_key,
            }
            payload = {
                "active_profile_id": "default",
                "profiles": [bootstrap_profile],
            }
            self._write_payload(payload)
        payload = self._normalize_payload(payload)
        self._write_payload(payload)
        return LLMSettingsResponse(
            active_profile_id=payload.get("active_profile_id"),
            profiles=[self._to_response(profile) for profile in payload.get("profiles", [])],
        )

    async def upsert_profile(self, request: LLMProfileUpsert) -> LLMSettingsResponse:
        payload = self._read_payload()
        profiles = payload.get("profiles", [])
        profile_id = request.profile_id or f"profile_{uuid.uuid4().hex[:8]}"

        existing = next((item for item in profiles if item.get("profile_id") == profile_id), None)
        api_key = request.api_key
        if existing is not None and not api_key:
            api_key = str(existing.get("api_key", ""))
        profile_record = {
            "profile_id": profile_id,
            "name": request.name,
            "provider": request.provider,
            "model": request.model,
            "base_url": request.base_url,
            "api_key": api_key,
        }

        if existing is None:
            profiles.append(profile_record)
        else:
            existing.update(profile_record)

        if not payload.get("active_profile_id"):
            payload["active_profile_id"] = profile_id

        payload["profiles"] = profiles
        self._write_payload(payload)
        return await self.activate_profile(LLMActivateRequest(profile_id=payload["active_profile_id"]))

    async def activate_profile(self, request: LLMActivateRequest) -> LLMSettingsResponse:
        payload = self._read_payload()
        profiles = payload.get("profiles", [])
        if not any(item.get("profile_id") == request.profile_id for item in profiles):
            raise ValueError("Profile not found")

        payload["active_profile_id"] = request.profile_id
        self._write_payload(payload)

        refresh_settings()
        await reset_llm_adapter()
        reset_llm_health_cache()

        return self.get_settings_payload()
