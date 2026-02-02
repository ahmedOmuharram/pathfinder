"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, get_origin
import tomllib

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

    def get_field_value(self, field: object, field_name: str) -> tuple[object, str, bool]:
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

    # Database (SQLite for dev, PostgreSQL for prod)
    database_url: str = "sqlite+aiosqlite:///./pathfinder.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.0
    openai_top_p: float = 1.0

    # Sub-kani orchestration
    subkani_model: str = "gpt-4o"
    subkani_temperature: float = 0.0
    subkani_top_p: float = 1.0
    subkani_max_concurrency: int = 6
    subkani_timeout_seconds: int = 120

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.api_env == "development"

    @computed_field  # type: ignore[prop-decorator]
    @property
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

