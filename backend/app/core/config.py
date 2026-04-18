"""
LightClaw 配置管理
"""
from functools import lru_cache
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


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
