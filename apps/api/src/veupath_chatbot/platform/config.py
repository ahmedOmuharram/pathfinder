"""Application configuration using pydantic-settings."""

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal, get_origin

from pydantic import Field, computed_field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    """Load settings from a TOML config file."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        path = (Path(__file__).resolve().parents[3] / "config.toml").resolve()

        if not path.exists():
            self._data: dict[str, object] = {}
        else:
            with path.open("rb") as handle:
                self._data = tomllib.load(handle)

    def _is_complex_field(self, field: object) -> bool:
        annotation = getattr(field, "annotation", None)
        origin = get_origin(annotation) or annotation
        return origin in (list, dict, set, tuple)

    def get_field_value(
        self, field: object, field_name: str
    ) -> tuple[object, str, bool]:
        value = self._data.get(field_name)
        if value is None:
            return None, field_name, False
        if self._is_complex_field(field):
            if isinstance(value, (str, bytes, bytearray)):
                return value, field_name, True
            return value, field_name, False
        return value, field_name, False

    def __call__(self) -> dict[str, object]:
        data: dict[str, object] = {}
        for field_name, field in self.settings_cls.model_fields.items():
            value, key, is_complex = self.get_field_value(field, field_name)
            if value is None:
                continue
            if not isinstance(value, (str, bytes, bytearray)):
                data[key] = value
                continue
            value = self.prepare_field_value(field_name, field, value, is_complex)
            if value is not None:
                data[key] = value
        return data


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_env: Literal["development", "staging", "production"] = "development"
    api_debug: bool = False
    api_secret_key: str = Field(
        default="dev-only-secret-key-change-in-prod",
        min_length=32,
    )
    api_docs_enabled: bool = True

    # Database
    #
    # PathFinder uses SQL persistence for users/strategies/plan sessions. We default to
    # PostgreSQL even for local development so behavior matches Docker/production.
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/pathfinder"
    )

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.0
    openai_top_p: float = 1.0
    openai_hyperparams: dict[str, object] = Field(
        default_factory=dict,
        description="Extra OpenAI chat-completions params passed through to the engine.",
    )

    # Anthropic (Claude)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-0"
    anthropic_temperature: float = 0.0
    anthropic_top_p: float = 1.0
    anthropic_hyperparams: dict[str, object] = Field(default_factory=dict)

    # Google (Gemini)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"
    gemini_temperature: float = 0.0
    gemini_top_p: float = 1.0
    gemini_hyperparams: dict[str, object] = Field(default_factory=dict)

    # Retrieval / vector store (Qdrant)
    rag_enabled: bool = True
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_timeout_seconds: float = 10.0

    # RAG ingestion (startup background job)
    rag_startup_max_strategies_per_site: int | None = None
    rag_startup_public_strategies_concurrency: int | None = None
    rag_startup_public_strategies_llm_model: str = "gpt-4o-mini"
    rag_startup_public_strategies_report_path: str = (
        "/tmp/ingest_public_strategies_report.jsonl"
    )

    # Embeddings
    embeddings_model: str = "text-embedding-3-small"

    # Sub-kani orchestration
    subkani_model: str = "gpt-4o"
    subkani_temperature: float = 0.0
    subkani_top_p: float = 1.0
    subkani_max_concurrency: int = 6
    subkani_timeout_seconds: int = 120

    # Unified model defaults (applies to both planning and execution modes)
    default_model_id: str = "openai/gpt-5"
    default_reasoning_effort: Literal["none", "low", "medium", "high"] = "medium"

    # VEuPathDB
    veupathdb_default_site: str = "plasmodb"
    veupathdb_cache_ttl: int = 3600
    veupathdb_auth_token: str | None = None
    veupathdb_oauth_url: str | None = None
    veupathdb_oauth_client_id: str | None = None

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_origin_regex: str | None = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    @computed_field
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.api_env == "development"

    @computed_field
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.api_env == "production"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            TomlConfigSettingsSource(settings_cls),
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
