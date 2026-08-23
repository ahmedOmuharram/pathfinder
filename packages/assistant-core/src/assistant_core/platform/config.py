"""The settings the runtime reads, and where it reads them from."""

from collections.abc import Callable
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    """What the runtime needs to open a database, log, and stream.

    A host application extends this class with its own settings and installs
    the extended instance through ``use_settings_source``.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
    )

    database_url: str = Field(default="", repr=False)
    api_debug: bool = False

    # Seconds of silence after which a stream sends a comment frame.
    sse_keepalive_seconds: int = Field(default=15, ge=1)

    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"


@lru_cache
def _default_settings() -> RuntimeSettings:
    return RuntimeSettings()


class _SettingsSource:
    """Where the runtime reads its settings. The host may replace it once."""

    def __init__(self) -> None:
        self._read: Callable[[], RuntimeSettings] = _default_settings

    def use(self, read: Callable[[], RuntimeSettings]) -> None:
        self._read = read

    def read(self) -> RuntimeSettings:
        return self._read()


_source = _SettingsSource()


def use_settings_source(read: Callable[[], RuntimeSettings]) -> None:
    """Read settings from the host application instead of the environment."""
    _source.use(read)


def get_runtime_settings() -> RuntimeSettings:
    """The settings in force for this process."""
    return _source.read()
