"""Result shapes the served tools return where a service answers with a mapping."""

from __future__ import annotations

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import ConfigDict


class SearchCategory(CamelModel):
    """One ontology category of a site's searches, with example search names."""

    model_config = ConfigDict(frozen=True)

    category: str
    count: int
    examples: list[str]


class SearchListing(CamelModel):
    """One search of a record type, by name."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str


class TransformListing(CamelModel):
    """One search that accepts an input step, and what it does."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str
    description: str


class StepDownloadUrl(CamelModel):
    """Where one step's results download from, and in what format."""

    model_config = ConfigDict(frozen=True)

    step_id: int
    format: str
    download_url: str


__all__ = [
    "SearchCategory",
    "SearchListing",
    "StepDownloadUrl",
    "TransformListing",
]
