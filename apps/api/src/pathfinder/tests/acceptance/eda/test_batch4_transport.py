"""Acceptance: the seven EDA routes and the five-action PATCH union.

Values come from the live-verified EDA knowledge bundle. Fixtures are inline.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Iterator
from uuid import UUID, uuid4

import httpx
import pytest
from assistant_core.persistence.models import Conversation
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.tests.integration.http.conftest import (
    client_for,
    first_frame_client_for,
    make_user,
)

eda_router = pytest.importorskip("pathfinder.transport.http.routers.eda")
eda_client = pytest.importorskip("pathfinder.integrations.eda.client")
catalog = pytest.importorskip("pathfinder.services.eda.catalog")
authoring = pytest.importorskip("pathfinder.services.eda.authoring")
compute = pytest.importorskip("pathfinder.services.eda.compute")
repository = pytest.importorskip(
    "pathfinder.persistence.repositories.conversation_analysis"
)
parts = pytest.importorskip("shared_py.stream_parts.eda")

pytestmark = [pytest.mark.eda_acceptance]

_DATASET = "DS_53f554ec6a"
_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"
_SITE = "plasmodb"

_PERMISSIONS = {
    "perDataset": {
        _DATASET: {
            "studyId": "STUDY_53f554ec6a",
            "sha1Hash": "53f554ec6a4a9a7efebfe58e0303f2c7f84ec907",
            "isUserStudy": False,
            "displayName": "Rodent malaria phenotypes",
            "shortDisplayName": "Rodent phenotypes",
            "description": "Phenotype scores per gene",
            "type": "end-user",
            "actionAuthorization": {
                "studyMetadata": True,
                "subsetting": True,
                "visualizations": True,
                "resultsFirstPage": True,
                "resultsAll": True,
            },
        }
    }
}

_MULTI_FILTER = {
    "entityId": _ENTITY,
    "variableId": "CAT_1",
    "type": "multiFilter",
    "operation": "union",
    "subFilters": [
        {"variableId": "CHILD_1", "stringSet": ["Yes"]},
        {"variableId": "CHILD_2", "stringSet": ["Yes"]},
    ],
}


def _analysis_state(*, num_filters: int) -> object:
    return parts.EdaAnalysisState(
        site_id=_SITE,
        dataset_id=_DATASET,
        study_id="STUDY_53f554ec6a",
        analysis_id="t4fszEJ",
        revision=1,
        study_display_name="Rodent malaria phenotypes",
        display_name="berghei subset",
        num_filters=num_filters,
        num_computations=0,
        filters=[],
        filter_summaries=[],
        entity_counts=[],
        can_export_rows=False,
    )


@pytest.fixture
def permissions_only(monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    """One site's EDA service, answering /permissions and nothing else."""
    catalog.clear_study_caches()
    instance = eda_client.EdaClient(base_url="https://plasmodb.org/eda")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/permissions"):
            return httpx.Response(200, json=_PERMISSIONS)
        return httpx.Response(404, json={"status": "not-found"})

    instance.install_transport(httpx.MockTransport(handler))
    for module in (catalog, authoring, compute):
        monkeypatch.setattr(module, "get_eda_client", lambda _site: instance)
    token = veupathdb_auth_token_ctx.set("token-abc")
    yield instance
    veupathdb_auth_token_ctx.reset(token)
    catalog.clear_study_caches()


@pytest.fixture
async def signed_in(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
    signed_in_to_veupathdb: None,
) -> AsyncGenerator[tuple[httpx.AsyncClient, UUID]]:
    """A registered caller and a thread that caller owns.

    The registered-identity gate is the real one; the harness override
    stands in for the identity provider, as every WDK-backed route test does.
    """
    del patch_app_db_engine, db_cleaner, signed_in_to_veupathdb
    async with session_maker() as session:
        user = await make_user(session)
        thread = Conversation(id=uuid4(), user_id=user.id)
        session.add(thread)
        await session.commit()
    async with first_frame_client_for(app, user.id, wdk_token="token-abc") as client:
        yield client, thread.id


@pytest.mark.asyncio
async def test_a_caller_with_no_registered_login_is_refused_with_a_code(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> None:
    """EDA refuses a guest, so PathFinder mints nothing and answers 401."""
    del patch_app_db_engine, db_cleaner
    async with session_maker() as session:
        user = await make_user(session)
    async with client_for(app, user.id) as client:
        response = await client.get(
            "/api/v1/eda/studies", params={"siteId": _SITE, "q": "phenotype"}
        )
    assert response.status_code == 401
    assert response.json()["code"] == "WDK_LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_a_dataset_with_no_permission_entry_is_a_404_naming_the_id(
    signed_in: tuple[httpx.AsyncClient, UUID],
    permissions_only: object,
) -> None:
    client, _thread_id = signed_in
    response = await client.get(
        "/api/v1/eda/studies/EDAUD_slI5M0RwIg0Zw", params={"siteId": _SITE}
    )
    await permissions_only.close()
    assert response.status_code == 404
    assert "EDAUD_slI5M0RwIg0Zw" in json.dumps(response.json())


@pytest.mark.asyncio
async def test_a_count_body_naming_a_wire_absent_filter_type_is_a_422(
    signed_in: tuple[httpx.AsyncClient, UUID],
) -> None:
    """stringPrefixSet leaves the request model, so no wire call happens."""
    client, _thread_id = signed_in
    response = await client.post(
        "/api/v1/eda/count",
        params={"siteId": _SITE},
        json={
            "datasetId": _DATASET,
            "entityId": _ENTITY,
            "filters": [
                {
                    "entityId": _ENTITY,
                    "variableId": "VAR_035294d0",
                    "type": "stringPrefixSet",
                    "prefixSet": ["P. ber"],
                }
            ],
        },
    )
    assert response.status_code == 422
    assert "filters" in json.dumps(response.json())


@pytest.mark.asyncio
async def test_a_count_body_with_a_multi_filter_operation_outside_the_two_is_a_422(
    signed_in: tuple[httpx.AsyncClient, UUID],
) -> None:
    client, _thread_id = signed_in
    response = await client.post(
        "/api/v1/eda/count",
        params={"siteId": _SITE},
        json={
            "datasetId": _DATASET,
            "entityId": _ENTITY,
            "filters": [{**_MULTI_FILTER, "operation": "xor"}],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_viz_chart_the_route_does_not_serve_is_a_422(
    signed_in: tuple[httpx.AsyncClient, UUID],
) -> None:
    """The compute bridge supports volcano plots only."""
    client, _thread_id = signed_in
    response = await client.post(
        "/api/v1/eda/viz",
        params={"siteId": _SITE},
        json={
            "datasetId": _DATASET,
            "chart": "scatter",
            "effectSizeThreshold": 1.0,
            "significanceThreshold": 0.05,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_patch_action_outside_the_union_is_a_422(
    signed_in: tuple[httpx.AsyncClient, UUID],
) -> None:
    client, thread_id = signed_in
    response = await client.patch(
        f"/api/v1/conversations/{thread_id}/eda", json={"action": "rename"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_patch_body_that_names_no_action_is_a_422(
    signed_in: tuple[httpx.AsyncClient, UUID],
) -> None:
    """The union is discriminated on action, so a bare payload never dispatches."""
    client, thread_id = signed_in
    response = await client.patch(
        f"/api/v1/conversations/{thread_id}/eda", json={"filters": []}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unbinding_a_thread_that_has_nothing_open_leaves_it_unbound(
    signed_in: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    client, thread_id = signed_in
    response = await client.patch(
        f"/api/v1/conversations/{thread_id}/eda", json={"action": "unbind"}
    )
    assert response.status_code == 200
    assert response.json()["analysis"] is None
    repo = repository.ConversationAnalysesRepository(session_factory=session_maker)
    assert await repo.get(conversation_id=thread_id) is None


@pytest.mark.asyncio
async def test_setting_a_multi_filter_subset_answers_the_three_key_envelope(
    signed_in: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """multiFilter is the only way to express OR, and it reaches the service."""
    client, thread_id = signed_in
    await repository.ConversationAnalysesRepository(session_factory=session_maker).bind(
        conversation_id=thread_id,
        site_id=_SITE,
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
    )
    seen: list[object] = []

    async def apply(_site: str, **kwargs: object) -> object:
        seen.append(kwargs["filters"])
        return _analysis_state(num_filters=1)

    monkeypatch.setattr(eda_router, "apply_filters", apply)

    response = await client.patch(
        f"/api/v1/conversations/{thread_id}/eda",
        json={"action": "set-filters", "filters": [_MULTI_FILTER]},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"analysis", "job", "step"}
    assert body["job"] is None
    assert body["step"] is None
    assert body["analysis"]["numFilters"] == 1
    assert body["analysis"]["datasetId"] == _DATASET
    assert len(seen) == 1
    applied = seen[0]
    assert applied[0].operation == "union"
    assert [sub.variable_id for sub in applied[0].sub_filters] == [
        "CHILD_1",
        "CHILD_2",
    ]


@pytest.mark.asyncio
async def test_another_users_thread_is_absent_rather_than_forbidden(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
    signed_in_to_veupathdb: None,
) -> None:
    del patch_app_db_engine, db_cleaner, signed_in_to_veupathdb
    async with session_maker() as session:
        owner = await make_user(session)
        other = await make_user(session)
        thread = Conversation(id=uuid4(), user_id=owner.id)
        session.add(thread)
        await session.commit()
    async with first_frame_client_for(app, other.id, wdk_token="token-abc") as client:
        response = await client.get(f"/api/v1/conversations/{thread.id}/eda")
    assert response.status_code == 404
