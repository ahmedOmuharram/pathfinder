"""The conversation's bound analysis: read it, mutate it, and clear it."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from assistant_core.persistence.models import Conversation
from assistant_core.platform.types import JSONObject
from fastapi import FastAPI
from shared_py.stream_parts.eda import EdaAnalysisState
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.integrations.eda.models import (
    EdaAnalysisDescriptor,
    EdaAnalysisDetail,
    EdaComputeJob,
    EdaPermissionEntry,
    EdaStringSetFilter,
    EdaSubsetDescriptor,
)
from pathfinder.persistence.repositories.conversation_analysis import (
    ConversationAnalysesRepository,
)
from pathfinder.services.catalog.eda_backed import SUBSET_QUERY
from pathfinder.services.eda import authoring, binding, catalog
from pathfinder.services.eda.authoring import SubsetRejectedError
from pathfinder.services.strategies import commit
from pathfinder.services.strategies.commit import _WDKCommitOutcome
from pathfinder.tests.integration.http.conftest import (
    first_frame_client_for,
    make_user,
)
from pathfinder.transport.http.routers import eda as eda_router

pytestmark = pytest.mark.asyncio

_DATASET = "DS_53f554ec6a"
_STUDY = "STUDY_53f554ec6a"
_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"
_SPECIES = "VAR_035294d0"
_ANALYSIS = "t4fszEJ"

FIXTURES = (
    Path(__file__).resolve().parents[2] / "unit" / "integrations" / "eda" / "fixtures"
)


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def _detail() -> EdaAnalysisDetail:
    return EdaAnalysisDetail(
        analysis_id=_ANALYSIS,
        display_name="berghei subset",
        study_id=_DATASET,
        num_filters=1,
        num_computations=0,
        descriptor=EdaAnalysisDescriptor(
            subset=EdaSubsetDescriptor(
                descriptor=[
                    EdaStringSetFilter(
                        entity_id=_ENTITY,
                        variable_id=_SPECIES,
                        string_set=["P. berghei"],
                    )
                ]
            )
        ),
    )


def _analysis_state(*, num_filters: int) -> EdaAnalysisState:
    return EdaAnalysisState(
        site_id="plasmodb",
        dataset_id=_DATASET,
        study_id=_STUDY,
        analysis_id=_ANALYSIS,
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


def _computation_json() -> JSONObject:
    return {
        "type": "differentialexpression",
        "configuration": {
            "identifierVariable": {
                "entityId": _ENTITY,
                "variableId": "VAR_gene",
            },
            "valueVariable": {"entityId": _ENTITY, "variableId": "VAR_counts"},
            "comparator": {
                "variable": {"entityId": _ENTITY, "variableId": "VAR_state"},
                "groupA": [{"label": "febrile"}],
                "groupB": [{"label": "normal"}],
            },
        },
    }


def _wire(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/permissions"):
        return httpx.Response(200, json=_fixture("permissions.json"))
    if path == "/eda/studies":
        return httpx.Response(200, json=_fixture("studies_list.json"))
    if path == f"/eda/studies/{_STUDY}/entities/{_ENTITY}/count":
        filtered = json.loads(request.content)["filters"]
        name = "count_filtered.json" if filtered else "count_unfiltered.json"
        return httpx.Response(200, json=_fixture(name))
    if path == f"/eda/studies/{_STUDY}":
        return httpx.Response(200, json=_fixture("study_detail_phenotype.json"))
    return httpx.Response(404, json={"status": "not-found"})


@pytest.fixture
def eda_wired(monkeypatch: pytest.MonkeyPatch) -> Iterator[EdaClient]:
    """The phenotype study over the recorded wire, as this account sees it."""
    catalog.clear_study_caches()
    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(httpx.MockTransport(_wire))
    monkeypatch.setattr(catalog, "get_eda_client", lambda _s: client)
    monkeypatch.setattr(authoring, "get_eda_client", lambda _s: client)
    yield client
    catalog.clear_study_caches()


@pytest.fixture
async def thread(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
    signed_in_to_veupathdb: None,
) -> AsyncGenerator[tuple[httpx.AsyncClient, UUID]]:
    del patch_app_db_engine, db_cleaner, signed_in_to_veupathdb
    async with session_maker() as session:
        user = await make_user(session)
        conversation = Conversation(id=uuid4(), user_id=user.id)
        session.add(conversation)
        await session.commit()
    client = first_frame_client_for(app, user.id, wdk_token="test-token")
    async with client:
        yield client, conversation.id


async def _bind(
    session_maker: async_sessionmaker[AsyncSession], conversation_id: UUID
) -> None:
    await ConversationAnalysesRepository(session_factory=session_maker).bind(
        conversation_id=conversation_id,
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id=_ANALYSIS,
    )


async def test_an_unbound_thread_reads_as_no_analysis(
    thread: tuple[httpx.AsyncClient, UUID],
) -> None:
    client, conversation_id = thread
    response = await client.get(f"/api/v1/conversations/{conversation_id}/eda")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"analysis", "descriptor"}
    assert body["analysis"] is None
    assert body["descriptor"] is None


async def test_a_bound_thread_reads_the_analysis_state_and_the_descriptor(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    eda_wired: EdaClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tab hydrates from the same snapshot the part and the PATCH carry."""
    del eda_wired
    client, conversation_id = thread
    await _bind(session_maker, conversation_id)

    async def read(_site: str, *, analysis_id: str) -> EdaAnalysisDetail:
        assert analysis_id == _ANALYSIS
        return _detail()

    monkeypatch.setattr(eda_router, "read_analysis", read)

    response = await client.get(f"/api/v1/conversations/{conversation_id}/eda")
    assert response.status_code == 200
    body = response.json()
    analysis = body["analysis"]
    assert analysis["analysisId"] == _ANALYSIS
    assert analysis["datasetId"] == _DATASET
    assert analysis["siteId"] == "plasmodb"
    assert analysis["studyId"] == _STUDY
    assert analysis["studyDisplayName"]
    assert analysis["displayName"] == "berghei subset"
    assert analysis["numFilters"] == 1
    assert analysis["revision"] == 0
    assert analysis["filterSummaries"] == ["Species is one of P. berghei"]
    assert analysis["filters"][0]["stringSet"] == ["P. berghei"]
    assert analysis["canExportRows"] is True
    assert analysis["entityCounts"] == [
        {
            "entityId": _ENTITY,
            "entityDisplayName": "Gene Phenotype Data",
            "count": 4011,
            "unfilteredCount": 4279,
        }
    ]
    assert body["descriptor"]["subset"]["descriptor"][0]["stringSet"] == ["P. berghei"]


async def test_a_read_does_not_count_as_a_mutation(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    eda_wired: EdaClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hydration is read-only, so two GETs report the same revision."""
    del eda_wired
    client, conversation_id = thread
    await _bind(session_maker, conversation_id)

    async def read(_site: str, *, analysis_id: str) -> EdaAnalysisDetail:
        del analysis_id
        return _detail()

    monkeypatch.setattr(eda_router, "read_analysis", read)

    first = await client.get(f"/api/v1/conversations/{conversation_id}/eda")
    second = await client.get(f"/api/v1/conversations/{conversation_id}/eda")

    assert first.json()["analysis"]["revision"] == 0
    assert second.json()["analysis"]["revision"] == 0
    repo = ConversationAnalysesRepository(session_factory=session_maker)
    bound = await repo.get(conversation_id=conversation_id)
    assert bound is not None
    assert bound.revision == 0


async def test_patching_the_filters_replaces_the_subset(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, conversation_id = thread
    await _bind(session_maker, conversation_id)
    applied: list[object] = []

    async def apply(_site: str, **kwargs: object) -> EdaAnalysisState:
        applied.append(kwargs["filters"])
        return _analysis_state(num_filters=1)

    monkeypatch.setattr(eda_router, "apply_filters", apply)

    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={
            "action": "set-filters",
            "filters": [
                {
                    "entityId": _ENTITY,
                    "variableId": _SPECIES,
                    "type": "stringSet",
                    "stringSet": ["P. berghei"],
                }
            ],
        },
    )
    assert response.status_code == 200
    assert applied
    body = response.json()
    assert set(body) == {"analysis", "job", "step"}
    assert body["analysis"]["numFilters"] == 1
    assert body["analysis"]["revision"] == 1
    assert body["job"] is None
    assert body["step"] is None


async def test_patching_an_unbound_thread_is_a_conflict(
    thread: tuple[httpx.AsyncClient, UUID],
) -> None:
    """The thread exists, so the refusal is state, not absence."""
    client, conversation_id = thread
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={"action": "set-filters", "filters": []},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "EDA_NO_OPEN_ANALYSIS"


async def test_patching_an_invalid_filter_array_is_a_422_naming_the_value(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, conversation_id = thread
    await _bind(session_maker, conversation_id)

    async def rejects(_site: str, **_kwargs: object) -> EdaAnalysisState:
        raise SubsetRejectedError(["'P. vivax' is not a value of Species."])

    monkeypatch.setattr(eda_router, "apply_filters", rejects)

    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={
            "action": "set-filters",
            "filters": [
                {
                    "entityId": _ENTITY,
                    "variableId": _SPECIES,
                    "type": "stringSet",
                    "stringSet": ["P. vivax"],
                }
            ],
        },
    )
    assert response.status_code == 422
    assert "P. vivax" in json.dumps(response.json())


async def test_unbinding_clears_the_binding(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    client, conversation_id = thread
    repo = ConversationAnalysesRepository(session_factory=session_maker)
    await _bind(session_maker, conversation_id)
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda", json={"action": "unbind"}
    )
    assert response.status_code == 200
    assert response.json()["analysis"] is None
    assert await repo.get(conversation_id=conversation_id) is None


async def test_unbinding_an_unbound_thread_leaves_it_unbound(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Unbind is idempotent; the only 404 in the handler is the ownership check."""
    client, conversation_id = thread
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda", json={"action": "unbind"}
    )
    assert response.status_code == 200
    assert response.json()["analysis"] is None
    repo = ConversationAnalysesRepository(session_factory=session_maker)
    assert await repo.get(conversation_id=conversation_id) is None


async def test_bind_creates_the_upstream_analysis_and_the_row(
    thread: tuple[httpx.AsyncClient, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, conversation_id = thread
    seen: list[object] = []

    async def bind(site_id: str, **kwargs: object) -> EdaAnalysisState:
        seen.append((site_id, kwargs["dataset_id"], kwargs["conversation_id"]))
        return _analysis_state(num_filters=0)

    monkeypatch.setattr(eda_router, "bind_analysis", bind)
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={"action": "bind", "siteId": "plasmodb", "datasetId": _DATASET},
    )
    assert response.status_code == 200
    assert seen == [("plasmodb", _DATASET, conversation_id)]
    body = response.json()
    assert body["analysis"]["datasetId"] == _DATASET
    assert body["analysis"]["revision"] == 1
    assert body["job"] is None


async def test_run_compute_answers_with_the_job_reference(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, conversation_id = thread
    await _bind(session_maker, conversation_id)
    submitted: list[object] = []

    async def read(_site: str, *, analysis_id: str) -> EdaAnalysisDetail:
        del analysis_id
        return _detail()

    async def resolve(_site: str, dataset_id: str) -> EdaPermissionEntry:
        assert dataset_id == _DATASET
        return EdaPermissionEntry.model_validate({"studyId": _STUDY})

    async def submit(_site: str, **kwargs: object) -> EdaComputeJob:
        assert kwargs["study_id"] == _STUDY
        submitted.append(kwargs["compute_name"])
        return EdaComputeJob.model_validate(
            {"jobID": "db04204e5386396e1ca2cb78469ab6fb", "status": "queued"}
        )

    async def state(**_kwargs: object) -> EdaAnalysisState:
        return _analysis_state(num_filters=1)

    monkeypatch.setattr(eda_router, "read_analysis", read)
    monkeypatch.setattr(eda_router, "resolve_dataset", resolve)
    monkeypatch.setattr(eda_router, "submit_compute", submit)
    monkeypatch.setattr(eda_router, "mutated_analysis_state", state)

    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={"action": "run-compute", "computation": _computation_json()},
    )
    assert response.status_code == 200
    body = response.json()
    assert submitted == ["differentialexpression"]
    assert body["job"]["jobId"] == "db04204e5386396e1ca2cb78469ab6fb"
    assert body["job"]["status"] == "queued"
    assert body["job"]["taskId"] is None
    assert body["job"]["appName"] == "differentialexpression"
    assert body["analysis"]["revision"] == 1
    assert body["step"] is None


async def test_export_step_answers_with_the_refreshed_strategy(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, conversation_id = thread
    await _bind(session_maker, conversation_id)
    exported: list[object] = []

    async def export(**kwargs: object) -> JSONObject:
        thresholds = kwargs["thresholds"]
        exported.append(thresholds)
        return {"strategyId": 330423363, "name": "berghei subset"}

    async def state(**_kwargs: object) -> EdaAnalysisState:
        return _analysis_state(num_filters=1)

    monkeypatch.setattr(eda_router, "export_analysis_step", export)
    monkeypatch.setattr(eda_router, "mutated_analysis_state", state)

    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={
            "action": "export-step",
            "thresholds": {
                "effectSizeThreshold": 1.0,
                "significanceThreshold": 0.05,
                "effectDirection": "upAndDown",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["step"]["strategyId"] == 330423363
    assert body["analysis"]["revision"] == 1
    assert exported[0] is not None


async def test_export_step_on_a_thread_with_no_strategy_begins_it(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    eda_wired: EdaClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tab's first export is the thread's root step, through the real commit."""
    del eda_wired
    client, conversation_id = thread
    await _bind(session_maker, conversation_id)

    async def read(_site: str, *, analysis_id: str) -> EdaAnalysisDetail:
        del analysis_id
        return _detail()

    async def no_push(**_kwargs: object) -> _WDKCommitOutcome:
        return _WDKCommitOutcome(
            succeeded_step_ids=[], failed_step_ids=[], sync_result=None
        )

    monkeypatch.setattr(binding, "read_analysis", read)
    monkeypatch.setattr(commit, "_commit_to_wdk", no_push)

    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={"action": "export-step", "thresholds": None},
    )
    assert response.status_code == 200
    step = response.json()["step"]
    assert [leaf["searchName"] for leaf in step["steps"]] == [SUBSET_QUERY]
    assert step["rootStepId"] == step["steps"][0]["id"]


async def test_an_action_outside_the_union_is_a_422(
    thread: tuple[httpx.AsyncClient, UUID],
) -> None:
    client, conversation_id = thread
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={"action": "rename"},
    )
    assert response.status_code == 422


async def test_a_body_that_names_no_action_is_a_422(
    thread: tuple[httpx.AsyncClient, UUID],
) -> None:
    client, conversation_id = thread
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={"filters": []},
    )
    assert response.status_code == 422


async def test_another_users_thread_is_not_readable(
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
        conversation = Conversation(id=uuid4(), user_id=owner.id)
        session.add(conversation)
        await session.commit()
    async with first_frame_client_for(app, other.id, wdk_token="t") as client:
        read = await client.get(f"/api/v1/conversations/{conversation.id}/eda")
        written = await client.patch(
            f"/api/v1/conversations/{conversation.id}/eda",
            json={"action": "unbind"},
        )
    assert read.status_code == 404
    assert written.status_code == 404
