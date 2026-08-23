"""Which hidden required defaults return rows, and which return nothing.

A hidden required parameter is filled from ``initialDisplayValue``, and a
declared default has never meant "returns rows". This sweep runs every search
that carries one, binding every required parameter from its own published
default, and reads the count.

The sweep is long, so it is resumable: a completed search is read back from the
report file rather than asked again. ``WDK_HIDDEN_DEFAULTS_REPORT`` names the
file, ``WDK_HIDDEN_DEFAULTS_LIMIT`` caps how many searches one run measures.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from pathfinder.integrations.veupathdb.factory import get_wdk_client
from pathfinder.integrations.veupathdb.probe import WDKProbe
from pathfinder.tests.live.conftest import Probe
from pathfinder.tests.live.summary import DriftLog

pytestmark = [pytest.mark.live_wdk, pytest.mark.asyncio]

_SITE = "plasmodb"
_TRANSCRIPT = "/record-types/transcript/searches"
_REPORT_ENV = "WDK_HIDDEN_DEFAULTS_REPORT"
_LIMIT_ENV = "WDK_HIDDEN_DEFAULTS_LIMIT"
_DEFAULT_REPORT = Path("wdk-hidden-defaults.json")
_CONCURRENCY = 6
_NOTE_CHARS = 600


class HiddenParam(BaseModel):
    """One required parameter and the value WDK publishes for it."""

    model_config = ConfigDict(frozen=True)

    name: str
    param_type: str
    default: str
    visible: bool


class SearchMeasurement(BaseModel):
    """What one search answered when every published default was bound.

    ``unmeasurable`` marks a search with a required parameter that has no
    default to bind, so nothing can be run without choosing a value.
    """

    search: str
    hidden: list[HiddenParam]
    bound: dict[str, str] = Field(default_factory=dict)
    unmeasurable: list[str] = Field(default_factory=list)
    status: int = 0
    total_count: int | None = None
    note: str = ""

    @property
    def returned_nothing(self) -> bool:
        return self.status == 200 and self.total_count == 0


class SweepReport(BaseModel):
    """Every search measured so far, so a later run resumes rather than repeats."""

    site: str
    measured: dict[str, SearchMeasurement] = Field(default_factory=dict)


def _report_path() -> Path:
    named = os.environ.get(_REPORT_ENV)
    return Path(named) if named else _DEFAULT_REPORT


def _load_report() -> SweepReport:
    path = _report_path()
    if path.exists():
        return SweepReport.model_validate_json(path.read_text())
    return SweepReport(site=_SITE)


def _required_params(document: JsonValue) -> list[HiddenParam] | None:
    """Every required parameter of a search, with the default it publishes."""
    if not isinstance(document, dict):
        return None
    search_data = document.get("searchData")
    if not isinstance(search_data, dict):
        return None
    found: list[HiddenParam] = []
    for entry in search_data.get("parameters") or []:
        if not isinstance(entry, dict) or entry.get("allowEmptyValue", False):
            continue
        default = entry.get("initialDisplayValue")
        found.append(
            HiddenParam(
                name=str(entry["name"]),
                param_type=str(entry["type"]),
                default="" if default is None else str(default),
                visible=bool(entry.get("isVisible", True)),
            )
        )
    return found


async def _measure(search: str, required: list[HiddenParam]) -> SearchMeasurement:
    """Run the search with every published default bound, and read the count."""
    hidden = [p for p in required if not p.visible and p.default]
    without_a_default = sorted(p.name for p in required if not p.default)
    if without_a_default:
        return SearchMeasurement(
            search=search,
            hidden=hidden,
            unmeasurable=without_a_default,
            note="a required parameter publishes no default",
        )

    bound = {p.name: p.default for p in required}
    client = get_wdk_client(_SITE)
    try:
        result: WDKProbe = await client.probe(
            "POST",
            f"{_TRANSCRIPT}/{search}/reports/standard",
            json={
                "searchConfig": {"parameters": bound},
                "reportConfig": {"pagination": {"offset": 0, "numRecords": 0}},
            },
        )
    except httpx.HTTPError as exc:
        # A search that never answers is not a search that answered nothing.
        return SearchMeasurement(
            search=search, hidden=hidden, bound=bound, note=type(exc).__name__
        )
    body = result.json_body()
    total: int | None = None
    if result.status == 200 and isinstance(body, dict):
        meta = body.get("meta")
        if isinstance(meta, dict) and meta.get("totalCount") is not None:
            total = int(meta["totalCount"])
    return SearchMeasurement(
        search=search,
        hidden=hidden,
        bound=bound,
        status=result.status,
        total_count=total,
        note="" if result.status == 200 else result.text[:_NOTE_CHARS],
    )


async def _collect_searches(probe: Probe) -> list[str]:
    listing = await probe(_SITE, "GET", _TRANSCRIPT)
    assert listing.status == 200
    body = listing.json_body()
    assert isinstance(body, list)
    return [str(entry["urlSegment"]) for entry in body if isinstance(entry, dict)]


async def _hidden_by_search(
    probe: Probe, names: list[str]
) -> dict[str, list[HiddenParam]]:
    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def one(name: str) -> tuple[str, list[HiddenParam]]:
        async with semaphore:
            document = await probe(
                _SITE,
                "GET",
                f"{_TRANSCRIPT}/{name}",
                params={"expandParams": "true"},
            )
        if document.status != 200:
            return name, []
        return name, _required_params(document.json_body()) or []

    pairs = await asyncio.gather(*(one(name) for name in names))
    return {
        name: required
        for name, required in pairs
        if any(not p.visible and p.default for p in required)
    }


async def test_the_hidden_required_defaults_that_return_nothing_are_named(
    probe: Probe, drift_log: DriftLog
) -> None:
    """Measure every search whose hidden required parameters carry a default."""
    names = await _collect_searches(probe)
    hidden_by_search = await _hidden_by_search(probe, names)

    report = _load_report()
    outstanding = [s for s in sorted(hidden_by_search) if s not in report.measured]
    limit = int(os.environ.get(_LIMIT_ENV, "0"))
    if limit > 0:
        outstanding = outstanding[:limit]

    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def measure(search: str) -> SearchMeasurement:
        async with semaphore:
            return await _measure(search, hidden_by_search[search])

    for measurement in await asyncio.gather(*(measure(s) for s in outstanding)):
        report.measured[measurement.search] = measurement

    _report_path().write_text(report.model_dump_json(indent=2) + "\n")

    empty = sorted(m.search for m in report.measured.values() if m.returned_nothing)
    drift_log.record(
        site=_SITE,
        check="hidden-defaults-searches-carrying-one",
        subject="record-types/transcript",
        observed=len(hidden_by_search),
    )
    drift_log.record(
        site=_SITE,
        check="hidden-defaults-returning-zero",
        subject=json.dumps(empty[:20]),
        expected=0,
        observed=len(empty),
    )

    # The sweep names them; whether a zero is wrong is a per-search question.
    assert report.measured, "the sweep measured nothing"
