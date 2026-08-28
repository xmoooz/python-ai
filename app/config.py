import os
from functools import lru_cache

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROFILE = os.getenv("APP_ENV") or dotenv_values(".env").get("APP_ENV") or "dev"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{_PROFILE}"),
        env_file_encoding="utf-8",
    )

    app_env: str = "dev"
    debug: bool = True

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "app"
    postgres_password: str = "app"
    postgres_db: str = "app"

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
