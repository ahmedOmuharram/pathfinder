"""Dataset to study resolution, and the permission flags that gate an answer."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.services.eda import catalog

FIXTURES = Path(__file__).resolve().parents[2] / "integrations" / "eda" / "fixtures"

pytestmark = pytest.mark.asyncio


def _permissions() -> object:
    return json.loads((FIXTURES / "permissions.json").read_text())


@pytest.fixture(autouse=True)
def _clean_caches() -> None:
    catalog.clear_study_caches()


@pytest.fixture
def eda_client(monkeypatch: pytest.MonkeyPatch) -> EdaClient:
    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(
        httpx.MockTransport(lambda _r: httpx.Response(200, json=_permissions()))
    )
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)
    return client


@pytest.fixture(autouse=True)
def _token() -> Generator[None]:
    token = veupathdb_auth_token_ctx.set("t")
    yield
    veupathdb_auth_token_ctx.reset(token)


async def test_a_known_dataset_resolves_to_its_study_id(eda_client: EdaClient) -> None:
    entry = await catalog.resolve_dataset("plasmodb", "DS_53f554ec6a")
    assert entry.study_id == "STUDY_53f554ec6a"
    await eda_client.close()


async def test_resolution_never_derives_the_study_id_from_the_dataset_id(
    eda_client: EdaClient,
) -> None:
    """STUDY_<suffix> equals DS_<suffix> for only 684 of 747 curated studies."""
    entry = await catalog.resolve_dataset("plasmodb", "DS_dd73524c7e")
    assert entry.study_id == "STUDY_bf43a6913c"
    await eda_client.close()


async def test_an_unknown_dataset_raises_with_the_id_named(
    eda_client: EdaClient,
) -> None:
    with pytest.raises(catalog.UnknownEdaDatasetError) as excinfo:
        await catalog.resolve_dataset("plasmodb", "EDAUD_slI5M0RwIg0Zw")
    assert "EDAUD_slI5M0RwIg0Zw" in str(excinfo.value)
    await eda_client.close()


async def test_resolution_is_cached_per_site_so_one_call_serves_a_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_permissions())

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)

    await catalog.resolve_dataset("plasmodb", "DS_53f554ec6a")
    await catalog.resolve_dataset("plasmodb", "DS_16bc228c8e")
    await client.close()
    assert calls == ["/eda/permissions"]


def _routed(calls: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/permissions"):
            return httpx.Response(200, json=_permissions())
        if request.url.path.endswith("/studies"):
            return httpx.Response(
                200, json=json.loads((FIXTURES / "studies_list.json").read_text())
            )
        return httpx.Response(
            200,
            json=json.loads((FIXTURES / "study_detail_phenotype.json").read_text()),
        )

    return httpx.MockTransport(handler)


async def test_a_listed_dataset_reaches_a_cached_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The detail call takes the STUDY id, and only permissions supplies it."""
    calls: list[str] = []
    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(_routed(calls))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)

    entry, detail = await catalog.get_study_detail_for_dataset(
        "plasmodb", "DS_dd73524c7e"
    )
    again = await catalog.get_study_detail_for_dataset("plasmodb", "DS_dd73524c7e")
    await client.close()
    assert entry.study_id == "STUDY_bf43a6913c"
    assert detail.root_entity.id == "GENE_PHENOTYPE_DATA_ENTITY"
    assert again[1] is detail
    assert calls == [
        "/eda/permissions",
        "/eda/studies",
        "/eda/studies/STUDY_bf43a6913c",
    ]


async def test_a_dataset_whose_study_is_unlisted_reads_its_detail_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A study with no /studies row reports no version, so nothing caches it."""
    calls: list[str] = []
    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(_routed(calls))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)

    entry, detail = await catalog.get_study_detail_for_dataset(
        "plasmodb", "DS_53f554ec6a"
    )
    await catalog.get_study_detail_for_dataset("plasmodb", "DS_53f554ec6a")
    await client.close()
    assert entry.study_id == "STUDY_53f554ec6a"
    assert detail.id == "STUDY_53f554ec6a"
    assert calls.count("/eda/studies/STUDY_53f554ec6a") == 2


async def test_clearing_the_cache_forces_a_refetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_permissions())

    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(handler))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _site: client)

    await catalog.resolve_dataset("plasmodb", "DS_53f554ec6a")
    catalog.clear_study_caches()
    await catalog.resolve_dataset("plasmodb", "DS_53f554ec6a")
    await client.close()
    assert len(calls) == 2
