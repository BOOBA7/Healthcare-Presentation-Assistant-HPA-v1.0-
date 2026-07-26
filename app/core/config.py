from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from the .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = Field(
        default="openai",
        alias="LLM_PROVIDER",
    )

    openai_api_key: str = Field(
        default="",
        alias="OPENAI_API_KEY",
    )

    openai_model: str = Field(
        default="gpt-5.5",
        alias="OPENAI_MODEL",
    )

    gemini_api_key: str = Field(
        default="",
        alias="GEMINI_API_KEY",
    )

    gemini_model: str = Field(
        default="gemini-3.6-flash",
        alias="GEMINI_MODEL",
    )

    gemini_thinking_level: str = Field(
        default="low",
        alias="GEMINI_THINKING_LEVEL",
    )

    llm_temperature: float = Field(
        default=0.2,
        alias="LLM_TEMPERATURE",
    )

    # ==========================
    # Application
    # ==========================

    app_name: str = Field(
        default="Healthcare Presentation Assistant",
        alias="APP_NAME",
    )

    debug: bool = Field(
        default=True,
        alias="DEBUG",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value: object) -> object:
        if isinstance(value, str) and value.lower() in {"release", "production", "prod"}:
            return False
        return value


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    """
    return Settings()
