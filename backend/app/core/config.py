"""
LightClaw 配置管理
"""
from functools import lru_cache
import json
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "production", "testing"] = "development"
    app_debug: bool = True
    log_level: str = "INFO"

    # LLM Configuration
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.7
    llm_retry_count: int = 3
    llm_retry_backoff_ms: int = 1000

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/lightclaw.db"

    # Playwright
    headless_browser: bool = True
    browser_timeout: int = 30000  # ms

    # Search
    search_provider: str = "duckduckgo"
    search_timeout: int = 10
    search_max_results: int = 5
    search_retry_count: int = 3

    # Data paths
    data_dir: str = "./data"
    trajectories_dir: str = "./data/trajectories"
    screenshots_dir: str = "./data/screenshots"
    datapool_dir: str = "./data/datapool"
    exports_dir: str = "./data/exports"
    eval_dir: str = "./data/eval"

    # Agent settings
    max_steps: int = 20
    max_retries: int = 3

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


def _load_active_llm_profile(settings: Settings) -> dict | None:
    profile_path = Path(settings.data_dir) / "llm_profiles.json"
    if not profile_path.exists():
        return None

    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    active_profile_id = payload.get("active_profile_id")
    profiles = payload.get("profiles", [])
    if not active_profile_id or not isinstance(profiles, list):
        return None

    for profile in profiles:
        if profile.get("profile_id") == active_profile_id:
            return profile
    return None


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    settings = Settings()
    profile = _load_active_llm_profile(settings)
    if profile:
        settings.llm_provider = profile.get("provider", settings.llm_provider)
        settings.llm_model = profile.get("model", settings.llm_model)
        settings.llm_base_url = profile.get("base_url", settings.llm_base_url)
        settings.llm_api_key = profile.get("api_key", settings.llm_api_key)
    return settings


def refresh_settings() -> Settings:
    """清空缓存并重新加载配置"""
    get_settings.cache_clear()
    return get_settings()
