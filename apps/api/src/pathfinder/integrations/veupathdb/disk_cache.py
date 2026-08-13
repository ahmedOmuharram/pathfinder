"""Disk cache for catalog metadata snapshots."""

import json
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
)
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_CATALOG_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "catalogs"
_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


class CatalogSnapshot(BaseModel):
    """A snapshot of one site's catalog metadata."""

    model_config = ConfigDict(extra="ignore")

    cached_at: float = Field(default_factory=time.time)
    record_types: list[WDKRecordType]
    searches: dict[str, list[WDKSearch]]
    dataset_summaries: dict[str, str]
    dataset_contacts: dict[str, str]
    search_categories: dict[str, str]
    search_category_labels: dict[str, str] = Field(default_factory=dict)
    available_categories: list[str]

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.cached_at) > _CACHE_TTL_SECONDS


def catalog_cache_path(site_id: str) -> Path:
    return _CATALOG_CACHE_DIR / f"{site_id}.json"


def try_load_catalog_cache(site_id: str) -> CatalogSnapshot | None:
    """Loads a cached snapshot. A missing or unreadable file returns None."""
    path = catalog_cache_path(site_id)
    if not path.exists():
        return None
    try:
        raw = path.read_text()
        return CatalogSnapshot.model_validate_json(raw)
    except OSError, ValueError, json.JSONDecodeError:
        logger.debug("Catalog cache load failed", path=str(path))
        return None


def save_catalog_cache(site_id: str, snapshot: CatalogSnapshot) -> None:
    """Writes a catalog snapshot to disk."""
    _CATALOG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = catalog_cache_path(site_id)
    try:
        path.write_text(snapshot.model_dump_json(by_alias=True))
    except OSError:
        logger.warning("Failed to save catalog cache", path=str(path), exc_info=True)


# The models below parse the WDK dataset report.


class DatasetPkPart(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""
    value: str = ""


class DatasetAttributes(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str | None = None
    contact: str | None = None


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: list[DatasetPkPart] = Field(default_factory=list)
    attributes: DatasetAttributes = Field(default_factory=DatasetAttributes)

    @property
    def dataset_id(self) -> str:
        for part in self.id:
            if part.name == "dataset_id":
                return part.value
        return self.id[0].value if self.id else ""

    def populate(
        self,
        summaries: dict[str, str],
        contacts: dict[str, str],
    ) -> None:
        """Writes this record's summary and contact into the given maps."""
        ds_id = self.dataset_id
        if not ds_id:
            return
        if self.attributes.summary:
            summaries[ds_id] = self.attributes.summary
        if self.attributes.contact:
            contacts[ds_id] = self.attributes.contact


class DatasetReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    records: list[DatasetRecord] = Field(default_factory=list)
