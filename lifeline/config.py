"""Typed settings, read once from the environment / .env and validated at startup."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    # dev: default. demo: shows the demo-account table on the login page. prod: no demo conveniences.
    app_env: Literal["dev", "demo", "prod"] = "dev"
    db_backend: Literal["sqlite", "supabase"] = "sqlite"
    db_path: Path = ROOT / "lifeline.db"

    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    session_timeout_minutes: int = Field(default=30, ge=1, le=1440)
    login_max_attempts: int = Field(default=5, ge=1, le=20)
    login_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    bcrypt_rounds: int = Field(default=12, ge=4, le=15)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_file: Path = ROOT / "logs" / "lifeline.log"

    @model_validator(mode="after")
    def _backend_available(self) -> Settings:
        if self.db_backend != "sqlite":
            raise ValueError("DB_BACKEND=supabase is not implemented yet; use DB_BACKEND=sqlite")
        return self

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openrouter_api_key.get_secret_value().strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
