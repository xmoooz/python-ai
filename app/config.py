from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import quote_plus
import os

from dotenv import dotenv_values
from pydantic import Field, SecretStr, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class AppEnv(StrEnum):
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"
    PROD = "prod"


def detect_profile() -> AppEnv:
    """APP_ENV from the process, then `.env` only — not `.env.<profile>`."""
    raw = os.getenv("APP_ENV")
    if not raw:
        raw = dotenv_values(ROOT_DIR / ".env").get("APP_ENV")
    raw = (raw or AppEnv.DEV.value).strip().lower()
    try:
        return AppEnv(raw)
    except ValueError:
        allowed = ", ".join(env.value for env in AppEnv)
        raise ValueError(f"Invalid APP_ENV={raw!r}. Use one of: {allowed}") from None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
        frozen=True,
    )

    app_env: AppEnv = AppEnv.DEV
    app_name: str = "AI Microservice"
    app_version: str = "0.1.0"
    debug: bool = True
    enable_docs: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"

    host: str = "127.0.0.1"
    port: int = 8000

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "app"
    postgres_password: SecretStr = SecretStr("app")
    postgres_db: str = "app"
    postgres_pool_min_size: int = Field(default=2, ge=1)
    postgres_pool_max_size: int = Field(default=10, ge=1)

    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    job_ingestion_key: SecretStr | None = None
    job_source_hosts: list[str] = Field(default_factory=list)

    @field_validator("cors_origins", "job_source_hosts", mode="before")
    @classmethod
    def _split_list_setting(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return value
            return [part.strip() for part in stripped.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def _check_pool_and_prod(self) -> Self:
        if self.postgres_pool_min_size > self.postgres_pool_max_size:
            raise ValueError("POSTGRES_POOL_MIN_SIZE cannot exceed POSTGRES_POOL_MAX_SIZE")
        if self.app_env is AppEnv.PROD:
            if self.postgres_password.get_secret_value() in {"app", "changeme"}:
                raise ValueError("Set a real POSTGRES_PASSWORD when APP_ENV=prod")
        return self

    @computed_field
    @property
    def database_url(self) -> str:
        password = quote_plus(self.postgres_password.get_secret_value())
        return (
            f"postgresql://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def docs_url(self) -> str | None:
        return "/docs" if self.enable_docs else None

    @property
    def redoc_url(self) -> str | None:
        return "/redoc" if self.enable_docs else None

    @property
    def openapi_url(self) -> str | None:
        return "/openapi.json" if self.enable_docs else None


@lru_cache
def get_settings() -> Settings:
    profile = detect_profile()
    return Settings(
        _env_file=(ROOT_DIR / ".env", ROOT_DIR / f".env.{profile.value}"),
        app_env=profile,
    )
