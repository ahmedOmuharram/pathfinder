"""Writing one part of a search config keeps the rest of it.

A column filter narrows the answer and WDK counts it in ``estimatedSize``.
Rewriting the config from a subset of its keys drops that filter, widens the
result, and answers 204.
"""

from __future__ import annotations

from typing import Any

import pytest

from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.wdk_models import WDKFilterValue

_COLUMN_FILTERS: dict[str, Any] = {
    "gene_product": {"values": ["kinase"], "includeUnknown": False}
}

_STEP: dict[str, Any] = {
    "id": 9,
    "searchName": "GenesByMolecularWeight",
    "recordClassName": "transcript",
    "searchConfig": {
        "parameters": {"min_molecular_weight": "10000"},
        "filters": [{"name": "existing_filter", "disabled": False, "value": None}],
        "columnFilters": _COLUMN_FILTERS,
        "wdkWeight": 7,
    },
}


class _Recorder:
    """Captures the PUT body instead of reaching WDK."""

    def __init__(self) -> None:
        self.bodies: list[dict[str, Any]] = []

    async def __call__(
        self, path: str, json: dict[str, Any] | None = None, **_: object
    ) -> Any:
        del path
        self.bodies.append(json or {})
        return None

    @property
    def body(self) -> dict[str, Any]:
        return self.bodies[-1]


async def _read_step(path: str, **_: object) -> Any:
    del path
    return _STEP


def _client(monkeypatch: pytest.MonkeyPatch) -> tuple[VEuPathDBClient, _Recorder]:
    client = VEuPathDBClient("https://example.invalid/service")
    put = _Recorder()
    monkeypatch.setattr(client, "get", _read_step)
    monkeypatch.setattr(client, "put", put)
    return client, put


async def _set_one(client: VEuPathDBClient) -> None:
    await client.update_step_filters(
        "1", 9, [WDKFilterValue(name="new_filter", value=None, disabled=False)]
    )


class TestTheRestOfTheConfigSurvives:
    @pytest.mark.asyncio
    async def test_column_filters_are_kept(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, put = _client(monkeypatch)

        await _set_one(client)

        assert put.body["columnFilters"] == _COLUMN_FILTERS

    @pytest.mark.asyncio
    async def test_parameters_are_kept(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, put = _client(monkeypatch)

        await _set_one(client)

        assert put.body["parameters"] == {"min_molecular_weight": "10000"}

    @pytest.mark.asyncio
    async def test_the_weight_is_kept(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, put = _client(monkeypatch)

        await _set_one(client)

        assert put.body["wdkWeight"] == 7


class TestTheFiltersAreReplaced:
    @pytest.mark.asyncio
    async def test_the_new_filter_is_written(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, put = _client(monkeypatch)

        await _set_one(client)

        assert [f["name"] for f in put.body["filters"]] == ["new_filter"]

    @pytest.mark.asyncio
    async def test_view_filters_are_not_sent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # viewFilters does not belong to searchConfig; WDK's schema rejects it.
        client, put = _client(monkeypatch)

        await _set_one(client)

        assert "viewFilters" not in put.body
