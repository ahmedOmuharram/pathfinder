---
type: Plan
title: "EDA batch 4: transport and types"
description: The REST router the EDA tab hydrates from, and the type plumbing that carries the three data-eda part kinds into the generated TypeScript - two implementers, one verifier.
tags: [eda, pathfinder, plan, batch, transport, http, openapi, shared-ts, zod]
generated: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
status: accepted
---

# EDA batch 4: transport and types

**Goal.** Give the frontend everything it needs to exist: a REST surface the EDA
tab hydrates from, and the three `data-eda.*` kinds present in the shared
TypeScript union with real payload types, real zod schemas, and renderers that
compile.

**Prerequisites.** Batch 3 closed by the session lead. The three stream parts
are registered and the services they wrap are green.

**Read first:** [overview.md](overview.md) - the pinned Transport and Frontend
blocks - then [batch-2-services.md](batch-2-services.md) and
[batch-3-conversational-backend.md](batch-3-conversational-backend.md) for the
services and the part payloads this batch exposes, and
[../pathfinder-architecture-fit.md](../pathfinder-architecture-fit.md) section
3.4 for why the part kinds go into an open union.

## Inherited constraints

- **TDD is non-negotiable.** Failing test first, always.
- **Pydantic maximalism.** Every response model is a `CamelModel`. No raw dicts
  out of a route, no `isinstance` chains, no `getattr` with a default, no
  `hasattr`.
- **No type suppressions.** No `# type: ignore`, no `as any`, no
  `// @ts-ignore`, no `// @ts-expect-error`, no `eslint-disable`, no `noqa`. Fix
  the root cause.
- **No `import as`** in Python. The one exception is a genuine third-party name
  conflict.
- **No backwards compatibility.** No aliases, no re-exports as a compatibility
  device, no `TYPE_CHECKING` imports.
- **Comments: 1 to 3 lines, ASD-STE100, near zero.** No history, no incidents.
- **ASCII punctuation only.**
- **Import-linter:** `pathfinder.transport` may not import
  `pathfinder.integrations` or `pathfinder.persistence`. Every route calls
  `pathfinder.services`.
- **Frontend boundaries** (`apps/web/scripts/check-boundaries.mjs`): a feature
  imports only its own tree, `@/lib/`, `@/state/`, `@pathfinder/shared`,
  `@pathfinder/assistant-client` and third-party. `lib/` imports nothing from
  `features/`, `state/` or `app/`.
- **React:** no `useEffect`, no `useMemo`, no `useCallback`, no `memo` (React
  Compiler).
- **Generated output is committed.** When a Pydantic schema changes, the
  regenerated `packages/spec/openapi.json` and
  `packages/shared-ts/src/generated/` land in the same task.
- **Only the LLM is mocked.** The HTTP tests use the real app, the real
  database and the recorded EDA fixtures.
- **Definition of done.** Gates green plus zero debt plus adjacent
  reconciliation plus tests that assert correctness. The recap leads with
  remaining debt.

**Backend gate ladder:**

```bash
cd apps/api && uv run ruff check src/ \
  && uv run mypy --strict src/pathfinder/ \
  && uv run pyright src/pathfinder/ \
  && uv run pytest <the exact test files this task touched> -v
```

**Frontend gate ladder:**

```bash
cd apps/web && npx tsc --noEmit \
  && npx eslint src/ \
  && node scripts/check-boundaries.mjs \
  && npx vitest run <the exact test files this task touched>
```

---

## Implementer A: `transport/http/routers/eda.py`

### Files

| Action | Path |
|---|---|
| Create | `apps/api/src/pathfinder/transport/http/schemas/eda.py` |
| Create | `apps/api/src/pathfinder/transport/http/routers/eda.py` |
| Modify | `apps/api/src/pathfinder/main.py` (import and mount the router) |
| Modify | `apps/api/src/pathfinder/platform/error_handlers.py` (only if the EDA errors need a mapping the `AppError` handler does not already give - see task A1) |
| Create | `apps/api/src/pathfinder/tests/integration/http/test_eda_routes.py` |
| Create | `apps/api/src/pathfinder/tests/integration/http/test_conversation_eda_route.py` |

### Interfaces

**Consumes** (batches 2 and 3):

```python
from pathfinder.services.eda.catalog import (
    StudyCard, UnknownEdaDatasetError,
    get_study_detail_for_dataset, resolve_dataset, search_studies,
)
from pathfinder.services.eda.authoring import (
    SubsetPreview, SubsetRejectedError, apply_filters, preview_subset, verified_count,
)
from pathfinder.services.eda.compute import (
    RetainedSummary, read_statistics, retained_summary,
)
from pathfinder.services.eda.binding import (
    bound_conversation_analysis, read_analysis, unbind_conversation_analysis,
)
from pathfinder.services.eda import EdaFilter          # the re-export
```

**Produces:**

```python
# transport/http/schemas/eda.py
class EdaStudyListResponse(CamelModel)
class EdaStudySummaryResponse(CamelModel)
class EdaStudyDetailResponse(CamelModel)
class EdaEntityResponse(CamelModel)
class EdaVariableResponse(CamelModel)
class EdaCountRequest(CamelModel)
class EdaCountResponse(CamelModel)
class EdaDistributionRequest(CamelModel)
class EdaVizRequest(CamelModel)
class EdaVizResponse(CamelModel)
class ConversationEdaResponse(CamelModel)
class EdaBindAction(CamelModel)          # action: "bind"
class EdaSetFiltersAction(CamelModel)    # action: "set-filters"
class EdaRunComputeAction(CamelModel)    # action: "run-compute"
class EdaExportStepAction(CamelModel)    # action: "export-step"
class EdaUnbindAction(CamelModel)        # action: "unbind"
ConversationEdaPatchRequest              # the Discriminator("action") union of the five
class EdaJobRefResponse(CamelModel)      # job_id, task_id (None for tab-started), app_name, status
class EdaAnalysisPatchResponse(CamelModel)  # analysis, job, step

# transport/http/routers/eda.py
router: APIRouter      # composes the two sub-routers below
studies_router: APIRouter    # prefix /api/v1/eda
conversation_router: APIRouter  # prefix /api/v1/conversations
```

**The pinned routes, and they may not be renamed:**

| Method | Path |
|---|---|
| GET | `/api/v1/eda/studies?q=` |
| GET | `/api/v1/eda/studies/{dataset_id}` |
| POST | `/api/v1/eda/count` |
| POST | `/api/v1/eda/distribution` |
| POST | `/api/v1/eda/viz` |
| GET | `/api/v1/conversations/{conversation_id}/eda` |
| PATCH | `/api/v1/conversations/{conversation_id}/eda` |

---

### Task A1 - read the harness and decide the error mapping

This task writes no production code. Its output is two decisions the rest of the
section depends on, each recorded in the task's own commit message.

- [ ] **Read `apps/api/src/pathfinder/tests/integration/http/conftest.py`
      completely.** The idioms this section copies:
      - `client_for(app, user_id)` builds an `httpx.AsyncClient` over
        `httpx.ASGITransport` with the `X-Requested-With: XMLHttpRequest` header
        and a `pathfinder-auth` cookie from `create_user_token(user_id)`.
      - `first_frame_client_for(app, user_id, wdk_token)` adds the
        `X-VEUPATHDB-AUTH` header, which is the header the request resolver
        reads into `veupathdb_auth_token_ctx`. Every EDA route needs that
        header, because EDA refuses a guest.
      - `make_user(session)` inserts the `users` row the foreign keys need.
      - The `app` fixture is in `apps/api/src/pathfinder/tests/conftest.py` and
        clears the settings cache before `create_app()`.

- [ ] **Read `apps/api/src/pathfinder/transport/http/routers/memories.py` and
      `.../conversations/insert_saved.py` completely.** The idioms this section
      copies: a module-level `APIRouter(prefix=..., tags=[...])`, `CurrentUser`
      and `DBSession` from `transport/http/deps.py`, a `response_model=` on every
      route, a `CamelModel` request body, and `raise HTTPException(status_code=404, ...)`
      for a not-found.

- [ ] **Decide the error mapping, and write down which it is.** Read
      `apps/api/src/pathfinder/platform/error_handlers.py::app_error_handler`.
      The EDA errors from batch 1 all subclass `AppError` and carry a `status`,
      so the existing handler already turns each one into a problem+json
      response with that status. Two cases need a decision:
      - `UnknownEdaDatasetError` is a plain `Exception`, not an `AppError`. It
        must become a 404. Either make it subclass `NotFoundError` in
        `services/eda/catalog.py` (a batch-2 file, so this is an adjacent
        reconciliation and belongs in this task), or catch it in the router. Pick
        the subclass: the guidance string it already carries becomes the problem
        detail with no per-route code.
      - `SubsetRejectedError` must become a 422 with the per-filter errors in the
        `errors` array, so the tab can show them beside the filter that caused
        them. Make it subclass `ValidationError` from `platform/errors.py`,
        passing `errors=[{"message": e} for e in self.errors]`.
      Both changes are in `services/eda/`. Run the batch-2 and batch-3 suites
      after them; a test that asserted on the plain exception type must be
      updated in the same task, not later.

- [ ] Record both decisions in the task's recap, and confirm
      `grep -rn "except UnknownEdaDatasetError\|except SubsetRejectedError" apps/api/src/pathfinder/transport`
      finds nothing: the handler does the work.

---

### Task A2 - `GET /api/v1/eda/studies` and `GET /api/v1/eda/studies/{dataset_id}`

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/http/test_eda_routes.py`:

```python
"""The EDA REST surface the tab hydrates from."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.integrations.eda.client import EdaClient
from pathfinder.services.eda import authoring, catalog
from pathfinder.tests.integration.http.conftest import (
    first_frame_client_for,
    make_user,
)

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "unit"
    / "integrations"
    / "eda"
    / "fixtures"
)

pytestmark = pytest.mark.asyncio

_DATASET = "DS_53f554ec6a"
_STUDY = "STUDY_53f554ec6a"
_ENTITY = "GENE_PHENOTYPE_DATA_ENTITY"


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def _route(counts: list[int]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/permissions"):
            return httpx.Response(200, json=_fixture("permissions.json"))
        if path.endswith("/eda/studies"):
            return httpx.Response(200, json=_fixture("studies_list.json"))
        if path == f"/eda/studies/{_STUDY}":
            return httpx.Response(200, json=_fixture("study_detail_phenotype.json"))
        if path.endswith("/count"):
            return httpx.Response(200, json={"count": counts.pop(0)})
        if path.endswith("/distribution"):
            return httpx.Response(200, json=_fixture("distribution_categorical.json"))
        if "/visualizations/" in path:
            return httpx.Response(200, json=_fixture("volcano_statistics.json"))
        return httpx.Response(404, json={"status": "not-found"})

    return httpx.MockTransport(handler)


@pytest.fixture
async def eda_wired(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncGenerator[EdaClient]:
    from pathfinder.integrations.embeddings.semantic_index import set_cache_dir
    from pathfinder.services.eda import compute

    set_cache_dir(tmp_path)
    catalog.clear_study_caches()
    client = EdaClient(base_url="https://plasmodb.org/eda")
    client.install_transport(_route([4011, 4279]))
    for module in (catalog, authoring, compute):
        monkeypatch.setattr(module, "get_eda_client", lambda _s: client)
    yield client
    await client.close()


@pytest.fixture
async def api_client(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[tuple[httpx.AsyncClient, UUID]]:
    del patch_app_db_engine, db_cleaner
    async with session_maker() as session:
        user = await make_user(session)
    client = first_frame_client_for(app, user.id, wdk_token="test-token")
    async with client:
        yield client, user.id


async def test_a_study_search_answers_with_cards(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    del eda_wired
    client, _user_id = api_client
    response = await client.get(
        "/api/v1/eda/studies", params={"q": "phenotype", "siteId": "plasmodb"}
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["studies"], list)
    if body["studies"]:
        first = body["studies"][0]
        assert set(first) >= {
            "datasetId",
            "studyId",
            "displayName",
            "canSubset",
            "canExportRows",
            "relevance",
        }


async def test_a_study_search_with_no_query_lists_the_catalog(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    del eda_wired
    client, _user_id = api_client
    response = await client.get(
        "/api/v1/eda/studies", params={"siteId": "plasmodb"}
    )
    assert response.status_code == 200
    assert response.json()["studies"]


async def test_a_study_detail_carries_the_entity_tree_and_the_gene_entity(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    del eda_wired
    client, _user_id = api_client
    response = await client.get(
        f"/api/v1/eda/studies/{_DATASET}", params={"siteId": "plasmodb"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["datasetId"] == _DATASET
    assert body["studyId"] == _STUDY
    assert body["geneEntityId"] == _ENTITY
    entities = {e["entityId"] for e in body["entities"]}
    assert _ENTITY in entities
    variables = body["variables"]
    assert any(v["variableId"] == "VAR_035294d0" for v in variables)


async def test_an_unknown_dataset_is_a_404_naming_the_id(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    del eda_wired
    client, _user_id = api_client
    response = await client.get(
        "/api/v1/eda/studies/DS_nope", params={"siteId": "plasmodb"}
    )
    assert response.status_code == 404
    assert "DS_nope" in json.dumps(response.json())


async def test_a_request_with_no_wdk_token_is_refused(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> None:
    """EDA refuses a guest, so a request naming no registered login is a 401."""
    from pathfinder.tests.integration.http.conftest import client_for

    del patch_app_db_engine, db_cleaner
    async with session_maker() as session:
        user = await make_user(session)
    async with client_for(app, user.id) as client:
        response = await client.get(
            "/api/v1/eda/studies", params={"siteId": "plasmodb"}
        )
    assert response.status_code == 401
    assert response.json()["code"] == "WDK_LOGIN_REQUIRED"


async def test_a_missing_site_id_is_a_422(
    api_client: tuple[httpx.AsyncClient, UUID],
) -> None:
    client, _user_id = api_client
    response = await client.get("/api/v1/eda/studies")
    assert response.status_code == 422
```

- [ ] **Run it.** Expect 404 on every route: the router is not mounted.

- [ ] **Implementation.** Create
      `apps/api/src/pathfinder/transport/http/schemas/eda.py`. Every response
      model is a `CamelModel`, and the field sets mirror the tool return shapes
      of batch 3 so the tab and the chat show the same thing:

```python
"""Request and response shapes of the EDA routes."""

from __future__ import annotations

from typing import Literal

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field


class EdaStudySummaryResponse(CamelModel):
    dataset_id: str
    study_id: str
    display_name: str
    short_display_name: str = ""
    description: str = ""
    source_type: str = ""
    relevance: float = 0.0
    can_subset: bool = False
    can_export_rows: bool = False


class EdaStudyListResponse(CamelModel):
    studies: list[EdaStudySummaryResponse] = Field(default_factory=list)


class EdaVariableResponse(CamelModel):
    entity_id: str
    variable_id: str
    display_name: str
    variable_type: str
    filter_type: str | None = None
    data_shape: str | None = None
    is_multi_valued: bool = False
    vocabulary: list[str] = Field(default_factory=list)
    vocabulary_total: int = 0
    range_min: float | None = None
    range_max: float | None = None
    date_min: str | None = None
    date_max: str | None = None
    sub_filter_variable_ids: list[str] = Field(default_factory=list)


class EdaEntityResponse(CamelModel):
    entity_id: str
    display_name: str
    display_name_plural: str = ""
    parent_entity_id: str | None = None
    variable_count: int = 0
    has_gene_id: bool = False


class EdaStudyDetailResponse(CamelModel):
    dataset_id: str
    study_id: str
    display_name: str = ""
    entities: list[EdaEntityResponse] = Field(default_factory=list)
    variables: list[EdaVariableResponse] = Field(default_factory=list)
    gene_entity_id: str | None = None
    gene_entity_problem: str | None = None
    can_subset: bool = False
    can_export_rows: bool = False
```

  The variable list is the whole study's variables when the request names no
  entity, and one entity's when it does. A study with 4931 variables on one
  entity is real (`HMPWgs-1`), so the route takes an optional `entityId` query
  parameter and the tab asks per entity. Add that parameter and its test.

  Create `apps/api/src/pathfinder/transport/http/routers/eda.py`:

```python
"""HTTP routes for the EDA tab. Every route calls services only."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from pathfinder.services.eda import catalog
from pathfinder.transport.http.deps import (
    CurrentUser,
    RequiredSiteIdQuery,
    require_registered_wdk_identity,
)
from pathfinder.transport.http.schemas.eda import (
    EdaStudyDetailResponse,
    EdaStudyListResponse,
    EdaStudySummaryResponse,
)

studies_router = APIRouter(prefix="/api/v1/eda", tags=["eda"])
conversation_router = APIRouter(prefix="/api/v1/conversations", tags=["eda"])

_DEFAULT_STUDY_LIMIT = 20


@studies_router.get("/studies", response_model=EdaStudyListResponse)
async def list_eda_studies(
    site_id: RequiredSiteIdQuery,
    user_id: CurrentUser,
    q: Annotated[str, Query(max_length=500)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = _DEFAULT_STUDY_LIMIT,
) -> EdaStudyListResponse:
    """Search the studies this account can see, or list them when q is empty."""
    del user_id
    cards = (
        await catalog.search_studies(site_id, q, limit=limit)
        if q
        else await catalog.browse_studies(site_id, limit=limit)
    )
    return EdaStudyListResponse(
        studies=[_summary(card) for card in cards],
    )
```

  `catalog.browse_studies(site_id, limit)` does not exist yet. Add it in
  `services/eda/catalog.py` in this task: it lists the studies, drops the ones
  with no permission entry, orders them by `display_name`, and returns the same
  `StudyCard` list with `relevance` zero. Add its unit test beside the other
  catalog tests. Do not answer an empty query with an empty list: the tab's
  study picker opens with no query.

  The rest of the router follows the same shape. `_summary(card)` is a two-line
  builder; the detail route calls `catalog.get_study_detail_for_dataset` and
  builds the entity and variable lists with the SAME helper the tool uses. Put
  that helper in `services/eda/catalog.py` as
  `describe_study(entry, study, entity_id=None) -> StudyDescription` and have
  both `ai/tools/standalone/eda_catalog.py::describe_eda_study` and this route
  call it. Two builders would drift, and the tab and the chat would disagree
  about the same study. That refactor of the batch-3 tool is an adjacent
  reconciliation and belongs in this task.

- [ ] **Mount the router.** In `main.py`, add `eda` to the
      `from pathfinder.transport.http.routers import (...)` block in
      alphabetical position, and add `eda.router` to the tuple in
      `_register_routers`. Compose the two sub-routers in `eda.py`:

```python
router = APIRouter()
for eda_router in (studies_router, conversation_router):
    router.include_router(
        eda_router,
        dependencies=[Depends(require_registered_wdk_identity)],
    )
```

  Every EDA route reads a VEuPathDB account, so the gate is on the composed
  router rather than per route - the same shape
  `routers/conversations/__init__.py` uses for its `_WDK_BACKED` group.

- [ ] **Gates**, with
      `src/pathfinder/tests/integration/http/test_eda_routes.py` and
      `src/pathfinder/tests/integration/http/` whole (the authz matrix in that
      directory enumerates routes and may need the new ones added - read
      `_authz_matrix_cases.py` and add them if it does).

---

### Task A3 - `POST /count`, `POST /distribution`, `POST /viz`

- [ ] **Failing test.** Append to
      `apps/api/src/pathfinder/tests/integration/http/test_eda_routes.py`:

```python
async def test_count_answers_with_the_service_count(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    del eda_wired
    client, _user_id = api_client
    response = await client.post(
        "/api/v1/eda/count",
        params={"siteId": "plasmodb"},
        json={
            "datasetId": _DATASET,
            "entityId": _ENTITY,
            "filters": [
                {
                    "entityId": _ENTITY,
                    "variableId": "VAR_035294d0",
                    "type": "stringSet",
                    "stringSet": ["P. berghei"],
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4011
    assert body["unfilteredCount"] == 4279


async def test_count_refuses_an_out_of_vocabulary_value_with_a_422(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    """The service answers 200 with count 0, so the route must refuse first."""
    del eda_wired
    client, _user_id = api_client
    response = await client.post(
        "/api/v1/eda/count",
        params={"siteId": "plasmodb"},
        json={
            "datasetId": _DATASET,
            "entityId": _ENTITY,
            "filters": [
                {
                    "entityId": _ENTITY,
                    "variableId": "VAR_035294d0",
                    "type": "stringSet",
                    "stringSet": ["P. vivax"],
                }
            ],
        },
    )
    assert response.status_code == 422
    assert "P. vivax" in json.dumps(response.json())


async def test_count_refuses_an_unknown_filter_type_with_a_422(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    """The discriminated union refuses stringPrefixSet before any wire call."""
    del eda_wired
    client, _user_id = api_client
    response = await client.post(
        "/api/v1/eda/count",
        params={"siteId": "plasmodb"},
        json={
            "datasetId": _DATASET,
            "entityId": _ENTITY,
            "filters": [
                {
                    "entityId": _ENTITY,
                    "variableId": "V",
                    "type": "stringPrefixSet",
                    "prefixSet": ["ab"],
                }
            ],
        },
    )
    assert response.status_code == 422


async def test_distribution_answers_with_labels_and_values_of_equal_length(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    del eda_wired
    client, _user_id = api_client
    response = await client.post(
        "/api/v1/eda/distribution",
        params={"siteId": "plasmodb"},
        json={
            "datasetId": _DATASET,
            "entityId": _ENTITY,
            "variableId": "VAR_035294d0",
            "filters": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["labels"]) == len(body["values"])
    assert body["numVarValues"] == 8409
    assert body["isMultiValued"] is True


async def test_viz_answers_with_the_thresholded_volcano(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    del eda_wired
    client, _user_id = api_client
    response = await client.post(
        "/api/v1/eda/viz",
        params={"siteId": "plasmodb"},
        json={
            "datasetId": _DATASET,
            "chart": "volcano",
            "effectSizeThreshold": 1.0,
            "significanceThreshold": 0.05,
            "effectDirection": "upAndDown",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["chart"] == "volcano"
    assert body["totalPoints"] > 0
    assert body["retainedPoints"] <= body["totalPoints"]
    assert body["points"]
    assert all(
        set(p) >= {"pointId", "effectSize", "retained"} for p in body["points"]
    )


async def test_viz_on_an_analysis_with_no_computation_is_a_409(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    """The visualization endpoint never starts a compute."""
    del eda_wired
    client, _user_id = api_client
    response = await client.post(
        "/api/v1/eda/viz",
        params={"siteId": "plasmodb"},
        json={
            "datasetId": "DS_66f9e70b8a",
            "chart": "volcano",
            "effectSizeThreshold": 1.0,
            "significanceThreshold": 0.05,
        },
    )
    assert response.status_code == 409
    assert "compute" in json.dumps(response.json()).lower()


async def test_a_chart_kind_outside_the_union_is_a_422(
    api_client: tuple[httpx.AsyncClient, UUID], eda_wired: EdaClient
) -> None:
    del eda_wired
    client, _user_id = api_client
    response = await client.post(
        "/api/v1/eda/viz",
        params={"siteId": "plasmodb"},
        json={"datasetId": _DATASET, "chart": "pie"},
    )
    assert response.status_code == 422
```

- [ ] **Implementation.** The three request models, in
      `transport/http/schemas/eda.py`:

```python
class EdaCountRequest(CamelModel):
    dataset_id: str
    entity_id: str
    filters: list[EdaFilter] = Field(default_factory=list)


class EdaCountResponse(CamelModel):
    entity_id: str
    count: int
    unfiltered_count: int


class EdaDistributionRequest(CamelModel):
    dataset_id: str
    entity_id: str
    variable_id: str
    filters: list[EdaFilter] = Field(default_factory=list)


# The distribution route's response_model is shared_py.stream_parts.eda's
# EdaDistributionSeries: the part and the route answer with ONE shape, so the
# frontend holds a single distribution representation and the charts consume
# either source with no adapter.


class EdaVizRequest(CamelModel):
    dataset_id: str
    chart: Literal["volcano"]
    effect_size_threshold: float = 1.0
    significance_threshold: float = 0.05
    effect_direction: Literal["upOnly", "downOnly", "upAndDown"] = "upAndDown"


class EdaVizPointResponse(CamelModel):
    point_id: str
    effect_size: float
    p_value: float | None = None
    adjusted_p_value: float | None = None
    retained: bool = False


class EdaVizResponse(CamelModel):
    chart: Literal["volcano"]
    effect_size_label: str = ""
    effect_size_threshold: float
    significance_threshold: float
    effect_direction: str
    total_points: int = 0
    retained_points: int = 0
    points: list[EdaVizPointResponse] = Field(default_factory=list)
```

  `EdaFilter` is imported from `pathfinder.services.eda`, which is the
  re-export batch 3 added. `pathfinder.transport` may not import
  `pathfinder.integrations`, and `lint-imports` will say so if the import goes
  to the wrong module.

  The count and distribution routes call `authoring.verified_count` and
  `authoring.preview_subset` from the Consumes block; each runs the domain
  predicates itself and raises `SubsetRejectedError` before any wire call, and
  `verified_count` returns the pair `(count, unfiltered_count)` the response
  carries. There is no separate `validate_subset` call in the router.
  distribution, so an invalid array is a 422 rather than a plausible zero.
  `SubsetRejectedError` becoming a `ValidationError` (task A1) is what makes that one
  line rather than a try/except.

  The `/viz` route reads the analysis bound to no conversation - it takes a
  `datasetId` and reads the computation from the analysis the CONVERSATION has
  open. That is wrong for a stateless route. Decide it here and write it down:
  the `/viz` route takes an explicit `conversationId` query parameter, reads the
  bound analysis, and 409s when the analysis carries no computation. Add the
  parameter to `EdaVizRequest` and to the tests above before writing the route.

  `EdaComputeNotReadyError` from batch 1 carries status 400; the route must
  answer 409 for "the compute has not run yet", because 400 reads as a
  malformed request to a client. Map it once, in
  `platform/error_handlers.py` or by giving that class status 409 in
  `integrations/eda/errors.py`. Prefer the second: the status belongs to the
  meaning, and the client sees the same code from every caller.

- [ ] **Gates.**

---

### Task A4 - `GET|PATCH /api/v1/conversations/{id}/eda`

- [ ] **Failing test.** Create
      `apps/api/src/pathfinder/tests/integration/http/test_conversation_eda_route.py`:

```python
"""The conversation's bound analysis: read it, and clear it."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from assistant_core.persistence.models import Conversation
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.persistence.repositories.conversation_analysis import (
    ConversationAnalysesRepository,
)
from pathfinder.tests.integration.http.conftest import (
    first_frame_client_for,
    make_user,
)

pytestmark = pytest.mark.asyncio

_DATASET = "DS_53f554ec6a"


@pytest.fixture
async def thread(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[tuple[httpx.AsyncClient, UUID]]:
    del patch_app_db_engine, db_cleaner
    async with session_maker() as session:
        user = await make_user(session)
        conversation = Conversation(id=uuid4(), user_id=user.id)
        session.add(conversation)
        await session.commit()
    client = first_frame_client_for(app, user.id, wdk_token="test-token")
    async with client:
        yield client, conversation.id


async def test_an_unbound_thread_reads_as_no_analysis(
    thread: tuple[httpx.AsyncClient, UUID],
) -> None:
    client, conversation_id = thread
    response = await client.get(f"/api/v1/conversations/{conversation_id}/eda")
    assert response.status_code == 200
    body = response.json()
    assert body["analysisId"] is None
    assert body["datasetId"] is None


async def test_a_bound_thread_reads_the_reference_and_the_descriptor(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathfinder.transport.http.routers import eda as eda_router

    client, conversation_id = thread
    await ConversationAnalysesRepository(session_factory=session_maker).bind(
        conversation_id=conversation_id,
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
    )

    async def read(_site: str, *, analysis_id: str) -> object:
        assert analysis_id == "t4fszEJ"
        return _detail()

    monkeypatch.setattr(eda_router, "read_analysis", read)

    response = await client.get(f"/api/v1/conversations/{conversation_id}/eda")
    assert response.status_code == 200
    body = response.json()
    assert body["analysisId"] == "t4fszEJ"
    assert body["datasetId"] == _DATASET
    assert body["siteId"] == "plasmodb"
    assert body["numFilters"] == 1
    assert body["descriptor"]["subset"]["descriptor"][0]["stringSet"] == [
        "P. berghei"
    ]


async def test_patching_the_filters_replaces_the_subset(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathfinder.transport.http.routers import eda as eda_router

    client, conversation_id = thread
    await ConversationAnalysesRepository(session_factory=session_maker).bind(
        conversation_id=conversation_id,
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
    )
    applied: list[object] = []

    async def apply(_site: str, **kwargs: object) -> object:
        applied.append(kwargs["filters"])
        return _detail()

    monkeypatch.setattr(eda_router, "apply_filters", apply)

    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={
            "action": "set-filters",
            "filters": [
                {
                    "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
                    "variableId": "VAR_035294d0",
                    "type": "stringSet",
                    "stringSet": ["P. berghei"],
                }
            ],
        },
    )
    assert response.status_code == 200
    assert applied
    body = response.json()
    assert body["analysis"]["numFilters"] == 1
    assert body["job"] is None
    assert body["step"] is None


async def test_patching_an_unbound_thread_is_a_404(
    thread: tuple[httpx.AsyncClient, UUID],
) -> None:
    client, conversation_id = thread
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={"action": "set-filters", "filters": []},
    )
    assert response.status_code == 404


async def test_patching_an_invalid_filter_array_is_a_422_naming_the_value(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathfinder.services.eda.authoring import SubsetRejectedError
    from pathfinder.transport.http.routers import eda as eda_router

    client, conversation_id = thread
    await ConversationAnalysesRepository(session_factory=session_maker).bind(
        conversation_id=conversation_id,
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
    )

    async def rejects(_site: str, **_kwargs: object) -> object:
        raise SubsetRejectedError(["'P. vivax' is not a value of Species."])

    monkeypatch.setattr(eda_router, "apply_filters", rejects)

    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={
            "action": "set-filters",
            "filters": [
                {
                    "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
                    "variableId": "VAR_035294d0",
                    "type": "stringSet",
                    "stringSet": ["P. vivax"],
                }
            ],
        },
    )
    assert response.status_code == 422
    assert "P. vivax" in json.dumps(response.json())


async def test_patching_with_a_null_analysis_clears_the_binding(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    client, conversation_id = thread
    repo = ConversationAnalysesRepository(session_factory=session_maker)
    await repo.bind(
        conversation_id=conversation_id,
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
    )
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda", json={"action": "unbind"}
    )
    assert response.status_code == 200
    assert response.json()["analysis"] is None
    assert await repo.get(conversation_id=conversation_id) is None


async def test_another_users_thread_is_not_readable(
    app: FastAPI,
    patch_app_db_engine: None,
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    async with session_maker() as session:
        owner = await make_user(session)
        other = await make_user(session)
        conversation = Conversation(id=uuid4(), user_id=owner.id)
        session.add(conversation)
        await session.commit()
    client = first_frame_client_for(app, other.id, wdk_token="test-token")
    async with client:
        response = await client.get(f"/api/v1/conversations/{conversation.id}/eda")
    assert response.status_code == 404


def _detail() -> object:
    from pathfinder.integrations.eda.models import EdaAnalysisDetail

    return EdaAnalysisDetail.model_validate(
        {
            "analysisId": "t4fszEJ",
            "displayName": "berghei subset",
            "studyId": _DATASET,
            "numFilters": 1,
            "numComputations": 0,
            "descriptor": {
                "subset": {
                    "descriptor": [
                        {
                            "entityId": "GENE_PHENOTYPE_DATA_ENTITY",
                            "variableId": "VAR_035294d0",
                            "type": "stringSet",
                            "stringSet": ["P. berghei"],
                        }
                    ],
                    "uiSettings": {},
                },
                "computations": [],
                "starredVariables": [],
                "dataTableConfig": {},
                "derivedVariables": [],
            },
        }
    )
```

- [ ] **Implementation.** The two schemas:

```python
class ConversationEdaResponse(CamelModel):
    """The thread's bound analysis, with the upstream descriptor passed through."""

    site_id: str | None = None
    dataset_id: str | None = None
    study_id: str | None = None
    analysis_id: str | None = None
    display_name: str = ""
    num_filters: int = 0
    num_computations: int = 0
    descriptor: JSONObject | None = None


class EdaBindAction(CamelModel):
    """Open an analysis on a study and bind it to this thread."""

    action: Literal["bind"]
    site_id: str
    dataset_id: str


class EdaSetFiltersAction(CamelModel):
    """Replace the bound analysis's subset."""

    action: Literal["set-filters"]
    filters: list[EdaFilter] = Field(default_factory=list)


class EdaRunComputeAction(CamelModel):
    """Submit or poll the analysis's compute. Idempotent per input hash."""

    action: Literal["run-compute"]
    computation: EdaComputationSpec


class EdaExportStepAction(CamelModel):
    """Export the analysis's genes as a step in the thread's strategy."""

    action: Literal["export-step"]
    thresholds: VolcanoThresholds | None = None


class EdaUnbindAction(CamelModel):
    """Clear the thread's binding. The upstream analysis is kept.

    Idempotent: unbinding an unbound thread is 200 with analysis null, never
    a 404 - the only 404 in the handler is the ownership check. The frozen
    acceptance suite pins this.
    """

    action: Literal["unbind"]


ConversationEdaPatchRequest = Annotated[
    EdaBindAction
    | EdaSetFiltersAction
    | EdaRunComputeAction
    | EdaExportStepAction
    | EdaUnbindAction,
    Discriminator("action"),
]


class EdaJobRefResponse(CamelModel):
    """The compute job a run-compute action addressed."""

    job_id: str
    task_id: str | None = None
    app_name: str
    status: str


class EdaAnalysisPatchResponse(CamelModel):
    """Every PATCH answers with the analysis state the surfaces re-render from.

    ``analysis`` is always PRESENT and nullable, never omitted: the frozen
    acceptance suite refuses an envelope missing the key, and the generated
    zod schema must agree (nullable, required).
    """

    analysis: EdaAnalysisState | None = None
    job: EdaJobRefResponse | None = None
    step: JSONObject | None = None
```

`EdaComputationSpec` is a batch 2/3 model (the compute configuration the
authoring service builds); import it through `pathfinder.services.eda`, adding
it to the re-export if batch 3 did not. `VolcanoThresholds` does NOT exist yet
and is defined in this task, in `services/eda/compute.py`, as the typed form
of the keyword triple `retained_summary` already takes:

```python
class VolcanoThresholds(CamelModel):
    """The volcano cut both surfaces and the export share."""

    effect_size_threshold: float
    significance_threshold: float
    effect_direction: Literal["upOnly", "downOnly", "upAndDown"] = "upAndDown"
```

The wire spelling is `effectDirection`, the same as `EdaVizPart`; the
frontend's chart-prop type keeps its local `direction` name and maps at its
one wire call site. `EdaAnalysisState` is the SAME
`shared_py.stream_parts.eda` payload the `data-eda.analysis-state` part
carries, so the tab and the chat literally share one shape. `step` is the
regenerated strategy payload the strategy routes already return; build it with
the same service call `routers/conversations/crud.py::get_strategy` uses and
pass it through as `JSONObject`, so `lib/api/strategy.ts::toStrategy` parses
it with zero new frontend code.

The handler is a dispatch, not an if-ladder:

```python
@conversation_router.patch(
    "/{conversation_id}/eda", response_model=EdaAnalysisPatchResponse
)
async def patch_conversation_eda(
    conversation_id: UUID,
    body: ConversationEdaPatchRequest,
    user_id: CurrentUser,
    session: DBSession,
) -> EdaAnalysisPatchResponse:
    """Mutate the thread's bound analysis: bind, subset, compute, export, unbind."""
    await _owned_conversation_or_404(session, conversation_id, user_id)
    match body:
        case EdaBindAction():
            return await _bind(session, conversation_id, user_id, body)
        case EdaSetFiltersAction():
            return await _set_filters(session, conversation_id, body)
        case EdaRunComputeAction():
            return await _run_compute(session, conversation_id, body)
        case EdaExportStepAction():
            return await _export_step(session, conversation_id, user_id, body)
        case EdaUnbindAction():
            return await _unbind(session, conversation_id)
```

Every mutating helper (`_bind`, `_set_filters`, `_run_compute`,
`_export_step`) calls `services/eda/binding.py::bump_analysis_revision`
after its mutation and puts the returned int in the response's
`analysis.revision`, exactly as the agent tools do for the part; a PATCH
response with `revision: null` on a bound analysis is a defect.

Each `_helper` calls the SAME service function the corresponding agent tool
calls, and two of those functions must be extracted in this task as adjacent
reconciliation, exactly like `describe_study` in task A2:

- **`services/eda/binding.py::bind_analysis(site_id, dataset_id, conversation_id, user_id) -> EdaAnalysisState`**
  - the body of batch 3's `open_eda_analysis` tool minus the `ModelRetry`
  wrapping and the chunk emission. The tool becomes a thin wrapper over it.
- **`services/eda/steps.py::export_analysis_step(site_id, conversation_id, user_id, thresholds) -> JSONObject`**
  - the body of batch 3's `create_eda_step` tool steps 1 to 8 (read the bound
  analysis, decide subset against compute export, rebuild the volcano
  configuration, `serialize_spec` once, `EdaStepRequest`, `StrategyStepNode`,
  `apply_operations_and_commit`), returning the refreshed strategy payload.
  The tool keeps only argument coaching (`ModelRetry` for a half-specified
  threshold pair) and the narration.

`_run_compute` calls `services/eda/compute.py::run_analysis_compute`, which
reads the analysis, writes the computation into the document when the
document does not already carry that exact one, and then submits the job with
that analysis's filters, `autostart=True`. The document is the SSOT every
volcano reads, so the write comes before the job: a configuration the study
rejects starts none. Because the job id is an input hash, repeating the
identical action IS the poll: the tab calls it again, reads `status`, and
writes nothing. `task_id` is `None` on this path; it is set only when a
durable chat task already exists for the same job, which `services/tasks` can
answer by job id.

The PATCH writes NO conversation event. Chat reflects a tab edit when the
agent next emits a `data-eda.analysis-state` part; until then the tab's store
is ahead, which is exactly the reconcile rule batch 5's store implements
(server part wins, keyed by `analysisId` and `revision`).

- [ ] **Failing tests for the three new actions.** Append to
      `test_conversation_eda_route.py`, in the same monkeypatch style as the
      set-filters test:

```python
async def test_bind_creates_the_upstream_analysis_and_the_row(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathfinder.transport.http.routers import eda as eda_router

    client, conversation_id = thread

    async def bind(**kwargs: object) -> object:
        assert kwargs["dataset_id"] == _DATASET
        return _analysis_state(num_filters=0)

    monkeypatch.setattr(eda_router, "bind_analysis", bind)
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={"action": "bind", "siteId": "plasmodb", "datasetId": _DATASET},
    )
    assert response.status_code == 200
    assert response.json()["analysis"]["datasetId"] == _DATASET


async def test_run_compute_answers_with_the_job_reference(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathfinder.transport.http.routers import eda as eda_router

    client, conversation_id = thread
    await ConversationAnalysesRepository(session_factory=session_maker).bind(
        conversation_id=conversation_id,
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
    )

    async def run(_site: str, **_kwargs: object) -> object:
        from pathfinder.integrations.eda.models import EdaComputeJob

        return EdaComputeJob.model_validate(
            {"jobID": "db04204e5386396e1ca2cb78469ab6fb", "status": "queued"}
        )

    monkeypatch.setattr(eda_router, "run_analysis_compute", run)
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={
            "action": "run-compute",
            "computation": _computation_spec_json(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["job"]["jobId"] == "db04204e5386396e1ca2cb78469ab6fb"
    assert body["job"]["status"] == "queued"
    assert body["job"]["taskId"] is None


async def test_export_step_answers_with_the_refreshed_strategy(
    thread: tuple[httpx.AsyncClient, UUID],
    session_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathfinder.transport.http.routers import eda as eda_router

    client, conversation_id = thread
    await ConversationAnalysesRepository(session_factory=session_maker).bind(
        conversation_id=conversation_id,
        site_id="plasmodb",
        dataset_id=_DATASET,
        analysis_id="t4fszEJ",
    )

    async def export(**_kwargs: object) -> object:
        return {"strategyId": 330423363, "steps": {"1": {"searchName": "GenesByEdaSubset"}}}

    monkeypatch.setattr(eda_router, "export_analysis_step", export)
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


async def test_an_action_outside_the_union_is_a_422(
    thread: tuple[httpx.AsyncClient, UUID],
) -> None:
    client, conversation_id = thread
    response = await client.patch(
        f"/api/v1/conversations/{conversation_id}/eda",
        json={"action": "rename"},
    )
    assert response.status_code == 422
```

`_analysis_state(num_filters=...)` builds a real
`shared_py.stream_parts.eda.EdaAnalysisState`; `_computation_spec_json()`
returns the JSON form of a real `EdaComputationSpec` - write both helpers at
the top of the file from the batch-3 models, no dict-shaped stand-ins.

  `descriptor` is a `JSONObject` passthrough on purpose: the upstream document is
  the SSOT and the tab renders it, so a typed mirror here would be a third copy
  that drifts. It is produced by
  `detail.descriptor.model_dump(by_alias=True, mode="json")` and never
  reconstructed.

  Ownership: the GET and the PATCH both resolve the conversation for the current
  user first, and a thread the user does not own is a 404, not a 403. Read how
  `routers/conversations/crud.py::get_strategy` does it and use the same service
  call, so the two routes cannot disagree about ownership.

- [ ] **Regenerate the API surface.** This task adds routes and schemas, so:

  ```bash
  docker compose --env-file .env.dev up -d --build api worker web
  yarn generate:types
  ```

  and commit `packages/spec/openapi.json` plus
  `packages/shared-ts/src/generated/`. Implementer B owns the shared-ts changes;
  coordinate so the regeneration runs once, after both halves are in, rather than
  twice.

- [ ] **Section end.**

  ```bash
  cd apps/api && uv run ruff check src/ \
    && uv run mypy --strict src/pathfinder/ \
    && uv run pyright src/pathfinder/ \
    && uv run lint-imports \
    && uv run pytest src/pathfinder/tests/ -v
  ```

---

## Implementer B: the type plumbing

### Files

| Action | Path |
|---|---|
| Modify | `packages/shared-ts/src/types.ts` (the union, the payload map, the imports) |
| Modify | `packages/spec/openapi.json` (regenerated, committed) |
| Modify | `packages/shared-ts/src/generated/**` (regenerated, committed) |
| Create | `apps/web/src/features/conversation/content/edaDataParts.ts` |
| Create | `apps/web/src/features/conversation/content/parts/DataEdaAnalysisState.tsx` |
| Create | `apps/web/src/features/conversation/content/parts/DataEdaSubsetPreview.tsx` |
| Create | `apps/web/src/features/conversation/content/parts/DataEdaViz.tsx` |
| Modify | `apps/web/src/features/conversation/content/contentComponents.ts` (merge the third map) |
| Create | `apps/web/src/features/conversation/content/edaDataParts.test.ts` |
| Create | `apps/api/src/pathfinder/tests/unit/stream_parts/test_eda_kinds_match_shared_ts.py` |

### Interfaces

**Consumes** (batch 3): `shared_py.stream_parts.eda`'s six models, and the three
registered kinds.

**Produces:**

```ts
// packages/shared-ts/src/types.ts
type KnownDataPartKind = ... | "data-eda.analysis-state"
                            | "data-eda.subset-preview"
                            | "data-eda.viz";
interface DataPartPayloadMap {
  "data-eda.analysis-state": EdaAnalysisState;
  "data-eda.subset-preview": EdaSubsetPreview;
  "data-eda.viz": EdaViz;
}
export type { EdaAnalysisState, EdaSubsetPreview, EdaViz,
              EdaEntityCount, EdaDistributionSeries, EdaVolcanoPoint };

// apps/web/src/features/conversation/content/edaDataParts.ts
export type EdaDataPartKind = "data-eda.analysis-state"
                            | "data-eda.subset-preview"
                            | "data-eda.viz";
export const edaDataPartComponents: DataPartComponentMap<EdaDataPartKind>;
```

---

### Task B1 - the generation procedure, run once and written down

The generation is not "run a script". It has a hard prerequisite, and getting it
wrong produces a spec that silently misses the new schemas.

- [ ] **Read the root `package.json` script.** It is:

  ```
  "generate:types": "docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml exec api curl -s http://localhost:8000/openapi.json | python3 -m json.tool > packages/spec/openapi.json && yarn --cwd packages/shared-ts generate"
  ```

  It `exec`s into a RUNNING `api` container and reads that container's live
  `/openapi.json`. A container built before batch 3 and 4 serves the OLD spec, and
  the regeneration then drops every new schema without erroring.

- [ ] **The procedure, in this order, every time:**

  ```bash
  cd /Users/ahmedmuharram/repos/pathfinder
  docker compose --env-file .env.dev up -d --build api worker web
  # Prove the container holds this batch's code before trusting its spec.
  docker compose exec api grep -c "data-eda.analysis-state" \
    /app/apps/api/src/pathfinder/ai/eda_stream_parts.py
  docker compose exec api grep -c "api/v1/eda" \
    /app/apps/api/src/pathfinder/transport/http/routers/eda.py
  yarn generate:types
  git status --short packages/spec packages/shared-ts/src/generated
  ```

  A grep count of 0 means `up -d --build` built a new image and left the old
  container running. Add `--force-recreate` and check again. Do not run
  `yarn generate:types` until both greps are non-zero.

- [ ] **Verify the regeneration actually carried the new schemas:**

  ```bash
  python3 -c "import json; s=json.load(open('packages/spec/openapi.json')); \
    print(sorted(k for k in s['components']['schemas'] if 'Eda' in k))"
  grep -rn "edaAnalysisState\|EdaAnalysisState" packages/shared-ts/src/generated | head
  ```

  The schema index model `StreamPartsSchemaIndex` is what carries the part
  payloads into the spec, so `EdaAnalysisState`, `EdaSubsetPreviewPart` and
  `EdaVizPart` must all appear. If they do not, the registration hook is not
  composed (batch 3, task A1) and this is a FAIL to send back, not something to
  patch here.

- [ ] **Commit the regenerated output** in the same commit as the hand edits of
      task B2. A spec regenerated in one commit and consumed in another leaves
      the repository un-buildable in between.

---

### Task B2 - the shared union and the payload map

- [ ] **Failing test (backend side).** The one gate that catches a kind added on
      one side and not the other. Create
      `apps/api/src/pathfinder/tests/unit/stream_parts/test_eda_kinds_match_shared_ts.py`:

```python
"""The registered kinds and the TypeScript union say the same thing."""

from __future__ import annotations

import re
from pathlib import Path

from assistant_core.conversation.stream_parts.registry import StreamPartRegistry

from pathfinder.ai.eda_stream_parts import register_eda_stream_parts

TYPES_TS = (
    Path(__file__).resolve().parents[5].parents[1]
    / "packages"
    / "shared-ts"
    / "src"
    / "types.ts"
)

_KIND = re.compile(r'"(data-eda\.[a-z-]+)"')


def _declared_kinds() -> set[str]:
    return set(_KIND.findall(TYPES_TS.read_text()))


def test_every_registered_eda_kind_appears_in_the_typescript_union() -> None:
    registry = StreamPartRegistry()
    register_eda_stream_parts(registry)
    assert registry.kinds() <= _declared_kinds()


def test_the_typescript_union_declares_no_eda_kind_the_backend_does_not_emit(
) -> None:
    registry = StreamPartRegistry()
    register_eda_stream_parts(registry)
    assert _declared_kinds() <= registry.kinds()


def test_every_eda_kind_has_an_entry_in_the_payload_map() -> None:
    text = TYPES_TS.read_text()
    start = text.index("interface DataPartPayloadMap")
    end = text.index("}", start)
    body = text[start:end]
    for kind in _declared_kinds():
        assert f'"{kind}"' in body, kind
```

  `TYPES_TS`'s path arithmetic is fragile. Compute the repository root the way
  another test in the suite already does; find one with
  `grep -rn "parents\[" apps/api/src/pathfinder/tests | head` and copy its
  approach, or walk up until a directory containing `pnpm-workspace.yaml` or the
  root `package.json` is found. A wrong path makes this test pass by reading
  nothing.

- [ ] **Failing test (frontend side).** Create
      `apps/web/src/features/conversation/content/edaDataParts.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { dataPartComponents } from "./contentComponents";
import { edaDataPartComponents } from "./edaDataParts";

const EDA_KINDS = [
  "data-eda.analysis-state",
  "data-eda.subset-preview",
  "data-eda.viz",
] as const;

describe("eda data parts", () => {
  it("registers a renderer for every eda kind", () => {
    for (const kind of EDA_KINDS) {
      expect(edaDataPartComponents[kind]).toBeTypeOf("function");
    }
  });

  it("is merged into the composed map", () => {
    for (const kind of EDA_KINDS) {
      expect(dataPartComponents[kind]).toBe(edaDataPartComponents[kind]);
    }
  });

  it("adds no kind the composed map does not carry", () => {
    expect(Object.keys(edaDataPartComponents).sort()).toEqual(
      [...EDA_KINDS].sort(),
    );
  });
});
```

- [ ] **Run both.** The Python test fails on the union; the vitest file fails to
      resolve `./edaDataParts`.

- [ ] **Implementation (shared-ts).** In `packages/shared-ts/src/types.ts`:
      add the three kinds to `KnownDataPartKind` at the end of the list, add the
      three entries to `DataPartPayloadMap`, and import the six generated payload
      types into the existing `import type { ... }` block in alphabetical
      position. The generated names come from the regeneration in task B1; read
      them out of `packages/shared-ts/src/generated/` rather than guessing -
      the backend classes are `EdaAnalysisState`, `EdaSubsetPreviewPart` and
      `EdaVizPart`, and Kubb may or may not keep the `Part` suffix.

  Re-export the six under stable names beside the existing
  `export type GeneSetPart = GeneSetStreamPart;` line, so a component imports
  from `@pathfinder/shared` and never from `@pathfinder/shared/generated`.

- [ ] **Implementation (the three renderers).** `dataPartComponents` is typed
      `DataPartComponentMap<KnownDataPartKind>`, which is TOTAL over the union.
      Adding three kinds without three renderers breaks `tsc` for the whole app,
      so the renderers land in this task. They are text-only and real - batch 3's
      goal was "the conversational seam works end to end in chat (text-only
      rendering)" - and batch 7 replaces their bodies with charts.

  `apps/web/src/features/conversation/content/parts/DataEdaAnalysisState.tsx`:

```tsx
import type { EdaAnalysisState } from "@pathfinder/shared";

export function DataEdaAnalysisState({ data }: { data: EdaAnalysisState }) {
  return (
    <div
      data-testid="data-eda-analysis-state"
      className="my-2 rounded-md border border-border bg-card px-3 py-2 text-xs"
    >
      <div className="flex items-center gap-2">
        <span className="inline-block size-1.5 rounded-full bg-success" />
        <span className="font-medium">EDA analysis open</span>
      </div>
      <div className="mt-1 text-muted-foreground">
        <span className="font-medium text-foreground">
          {data.studyDisplayName || data.datasetId}
        </span>
        <span className="mx-1">&middot;</span>
        <span>
          {data.numFilters} {data.numFilters === 1 ? "filter" : "filters"}
        </span>
        {data.numComputations > 0 ? (
          <>
            <span className="mx-1">&middot;</span>
            <span>
              {data.numComputations}{" "}
              {data.numComputations === 1 ? "compute" : "computes"}
            </span>
          </>
        ) : null}
      </div>
      {data.filterSummaries.length > 0 ? (
        <ul className="mt-1 list-disc pl-4 text-muted-foreground">
          {data.filterSummaries.map((summary) => (
            <li key={summary}>{summary}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
```

  The separator is written above as the HTML entity `&middot;` because this
  document is ASCII only. `DataGeneSet.tsx` uses the literal glyph, so write the
  literal glyph in the real component and match its siblings; do not introduce a
  second separator style.

  `DataEdaSubsetPreview.tsx` renders each entity count as
  `<count> of <unfilteredCount> <entity display name>`, and when a distribution
  is present, the top three labels with their values plus the sentence
  "values do not sum to the record count" when `isMultiValued` is true.

  `DataEdaViz.tsx` renders `<retainedPoints> of <totalPoints> genes pass` with
  the thresholds and the effect-size label, and no chart. Batch 5 adds the
  chart foundation and batch 7 mounts it here.

  `apps/web/src/features/conversation/content/edaDataParts.ts`:

```ts
import { DataEdaAnalysisState } from "./parts/DataEdaAnalysisState";
import { DataEdaSubsetPreview } from "./parts/DataEdaSubsetPreview";
import { DataEdaViz } from "./parts/DataEdaViz";
import type { DataPartComponentMap } from "./dataPartComponentMap";

/** Parts of the EDA surface: the open analysis, the subset, the plot. */
export type EdaDataPartKind =
  | "data-eda.analysis-state"
  | "data-eda.subset-preview"
  | "data-eda.viz";

export const edaDataPartComponents: DataPartComponentMap<EdaDataPartKind> = {
  "data-eda.analysis-state": DataEdaAnalysisState,
  "data-eda.subset-preview": DataEdaSubsetPreview,
  "data-eda.viz": DataEdaViz,
};
```

  and in `contentComponents.ts`, merge the third map:

```ts
import { edaDataPartComponents } from "./edaDataParts";
...
export const dataPartComponents: DataPartComponentMap<KnownDataPartKind> = {
  ...coreDataPartComponents,
  ...strategyDataPartComponents,
  ...edaDataPartComponents,
};
```

- [ ] **Gates.**

  ```bash
  cd apps/web && npx tsc --noEmit \
    && npx eslint src/ \
    && node scripts/check-boundaries.mjs \
    && npx vitest run src/features/conversation/content/
  cd ../api && uv run pytest src/pathfinder/tests/unit/stream_parts/ -v
  ```

**Traps named:**

- `dataPartComponents` must stay total over `KnownDataPartKind`. A kind with no
  renderer is a `tsc` error for the whole app, not a runtime fallback: the
  fallback is only for kinds ABSENT from `KnownDataPartKind`.
- No `as any` and no `// @ts-expect-error` to get past the totality. If the type
  fights you, the payload type is wrong.
- No `useEffect`, no `useMemo`, no `useCallback`, no `memo`.

---

### Task B3 - the zod schemas the conversation feature uses

- [ ] **Read how it is done today, before writing anything.** The pattern is in
      `apps/web/src/features/conversation/content/parts/DataBackgroundTaskStarted.tsx`:

```ts
import { taskCompletedSchema } from "@pathfinder/shared/generated/zod/taskCompletedSchema";
import { taskProgressSchema } from "@pathfinder/shared/generated/zod/taskProgressSchema";
...
const parsed = taskProgressSchema.safeParse(part.data);
if (parsed.success && parsed.data.taskId === taskId) { ... }
```

  The zod schemas are GENERATED by Kubb from the OpenAPI spec, one file per
  schema under `packages/shared-ts/src/generated/zod/`. Nothing is hand-written.
  A component that must read a part off ANOTHER message's `parts` array validates
  it with `safeParse`, because the part came off the wire as `unknown`.

- [ ] **Confirm the three schemas were generated:**

  ```bash
  ls packages/shared-ts/src/generated/zod | grep -i eda
  ```

  Expect `edaAnalysisStateSchema.ts`, `edaSubsetPreviewPartSchema.ts` and
  `edaVizPartSchema.ts`, named after the backend classes. If the directory holds
  nothing matching, the regeneration did not carry the schema index and task B1
  was not completed correctly.

- [ ] **Failing test.** Append to
      `apps/web/src/features/conversation/content/edaDataParts.test.ts`:

```ts
import { edaAnalysisStateSchema } from "@pathfinder/shared/generated/zod/edaAnalysisStateSchema";
import { edaVizPartSchema } from "@pathfinder/shared/generated/zod/edaVizPartSchema";

describe("eda zod schemas", () => {
  it("accepts an analysis-state payload the backend emits", () => {
    const parsed = edaAnalysisStateSchema.safeParse({
      siteId: "plasmodb",
      datasetId: "DS_53f554ec6a",
      studyId: "STUDY_53f554ec6a",
      analysisId: "t4fszEJ",
      studyDisplayName: "Rodent malaria phenotypes",
      displayName: "berghei subset",
      numFilters: 1,
      numComputations: 0,
      filterSummaries: ["Species is one of P. berghei"],
      canExportRows: true,
    });
    expect(parsed.success).toBe(true);
  });

  it("rejects a payload missing the analysis id", () => {
    const parsed = edaAnalysisStateSchema.safeParse({
      siteId: "plasmodb",
      datasetId: "DS_x",
      studyId: "STUDY_x",
    });
    expect(parsed.success).toBe(false);
  });

  it("accepts a volcano point with no p-value", () => {
    const parsed = edaVizPartSchema.safeParse({
      datasetId: "DS_e973eadd57",
      analysisId: "t4fszEJ",
      chart: "volcano",
      effectSizeLabel: "log2(Fold Change)",
      totalPoints: 5511,
      retainedPoints: 1543,
      points: [
        { pointId: "PF3D7_MIT04200", effectSize: -1.49447459261845, retained: false },
      ],
    });
    expect(parsed.success).toBe(true);
  });
});
```

- [ ] **Implementation.** There is none to write: the schemas are generated. If
      a test above fails, the cause is one of three things and each has a
      different fix:
      - the payload model's field is required in Python and optional in the test
        payload: fix the test to send it, or make the field optional in
        `shared_py/stream_parts/eda.py` because the backend really does omit it,
        and regenerate.
      - the generated schema does not exist: task B1 was not completed.
      - the generated schema rejects a value the backend sends: the payload model
        and the emitted chunk disagree, which is a batch-3 FAIL to send back.

      Do not hand-write a zod schema and do not patch a generated file. That is
      the "one way to generate types" rule this repository already decided.

- [ ] **Use the schemas where a part is read off another message.** The three new
      renderers receive their `data` already typed, so none of them needs
      `safeParse` yet. Batch 7's co-edit loop reads the LATEST
      `data-eda.analysis-state` off the thread's parts, and that read does need
      `safeParse`. Do not add an unused import now: note in the recap that batch
      7 consumes `edaAnalysisStateSchema`, and let batch 7 add the import.

- [ ] **Gates.**

  ```bash
  cd apps/web && npx tsc --noEmit \
    && npx eslint src/ \
    && node scripts/check-boundaries.mjs \
    && npx vitest run src/features/conversation/content/
  cd ../../packages/shared-ts && yarn typecheck
  # shared-ts has no eslint of its own; apps/web's eslint covers it via the
  # pre-commit eslint-web hook, so `npx eslint src/` above is its lint gate
  ```

- [ ] **Section end.** Run the full frontend suite once:

  ```bash
  cd apps/web && npx tsc --noEmit && npx eslint src/ \
    && node scripts/check-boundaries.mjs && npx vitest run
  ```

---

## Verifier - covers implementers A and B

### Re-run

```bash
cd apps/api
uv run ruff check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/ -v

cd ../web
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
npx vitest run

cd ../../packages/shared-ts
yarn typecheck   # its lint runs through apps/web's eslint (pre-commit eslint-web)

cd ../assistant-client-ts
yarn test && yarn typecheck && yarn lint
```

The `assistant-client-ts` suite is in the ladder because it is the protocol's
consumer-side conformance gate. This batch adds part kinds to an OPEN union and
must therefore change nothing in that package; a failure there means something
EDA-shaped reached the protocol.

### Traps to hunt, by name

**Transport:**

1. **Reject a route name that differs from the pinned list**, in path, method or
   casing. Read the seven rows against the router.
2. **Reject a route that imports `pathfinder.integrations` or
   `pathfinder.persistence`.** `uv run lint-imports` catches it; also grep the
   router.
3. **Reject a raw dict returned from any route.** Every route has a
   `response_model=` and returns a `CamelModel`.
4. **Reject a route with no `require_registered_wdk_identity`.** EDA refuses a
   guest; a route without the gate returns a 401 from deep inside the client
   instead of a clean one at the edge. Confirm with the no-token test.
5. **Reject `UnknownEdaDatasetError` or `SubsetRejectedError` caught in the router.**
   They subclass `NotFoundError` and `ValidationError`, and the existing handler
   does the work. Two mappings would drift.
6. **Reject a 400 for "the compute has not run yet".** It is a 409, and the
   status belongs to the error class so every caller sees the same code.
7. **Reject a `/count` or `/distribution` whose service call skips the domain
   predicates.** The
   service answers 200 with count 0 for an out-of-vocabulary value, so the route
   is the only guard the tab has.
8. **Reject a second study-description builder.** The route and the tool must
   call one `catalog.describe_study`. Grep for the entity and variable list
   construction and count the sites.
9. **Reject a typed mirror of the analysis descriptor in the response.** It is a
   `JSONObject` passthrough; a mirror would be a third copy of the SSOT.
10. **Reject a 403 for another user's thread.** It is a 404: existence is not
    disclosed.
11. **Reject an empty `q` answering with an empty list.** The study picker opens
    with no query, so an empty query lists the catalog.
12. **Reject a route added without a row in the authz matrix**, if
    `tests/integration/http/_authz_matrix_cases.py` enumerates routes. Read that
    file and check.
13. **Reject a PATCH body that is not the five-member action union.** A bare
    `{"filters": [...]}` with no `action` is a 422; the batch-5 client sends
    the union and the two must agree.
14. **Reject a second binding or step-building body.** `bind_analysis` and
    `export_analysis_step` are extracted services; the batch-3 tools and this
    router call the same function. Grep for `apply_operations_and_commit` under
    `ai/tools/` and `transport/` - it appears in neither; it appears once,
    in `services/eda/steps.py`.
15. **Reject a PATCH that writes a conversation event.** Tab edits reach chat
    through the agent's next `data-eda.analysis-state` part, never through a
    transport-side chunk write.

**Types:**

13. **Reject a hand-written zod schema, or a patched generated file.**
    `git diff packages/shared-ts/src/generated` must show only regenerated
    content, and no file under `generated/zod/` may be edited by hand.
14. **Reject a spec regenerated against a stale container.** Confirm the two
    greps of task B1 were run: `EdaAnalysisState`, `EdaSubsetPreviewPart` and
    `EdaVizPart` must all be in
    `packages/spec/openapi.json` under `components.schemas`.
15. **Reject a kind in `KnownDataPartKind` with no `DataPartPayloadMap` entry**,
    and the reverse. The Python test asserts set equality both ways; run it.
16. **Reject a kind with no renderer.** `dataPartComponents` is total; the
    absence is a `tsc` error, so a green `tsc` with a missing renderer means
    someone widened a type.
17. **Reject `as any`, `// @ts-ignore`, `// @ts-expect-error` or
    `eslint-disable`** anywhere in the diff.
18. **Reject `useEffect`, `useMemo`, `useCallback` or `memo`** in the three new
    components.
19. **Reject a component importing from `@pathfinder/shared/generated`** rather
    than from `@pathfinder/shared`. The re-export is what keeps the generated
    path an implementation detail. The zod schemas are the one exception, because
    that is how `DataBackgroundTaskStarted.tsx` already imports them.
20. **Reject a boundary violation.** `node scripts/check-boundaries.mjs` must
    pass, and the three components must import only from their own tree,
    `@/lib`, `@/state`, `@pathfinder/shared` and third-party.
21. **Reject an unused import added "for batch 7".** The recap names the
    pending consumer; the import lands with its consumer.
22. **Reject uncommitted regenerated output.**
    `git status --short packages/spec packages/shared-ts/src/generated` must be
    clean after the regeneration.

### Report format

One block per task (A1 to A4, B1 to B3):

```
Task A2 - PASS
  evidence: uv run pytest .../test_eda_routes.py -v -> 6 passed
  read: transport/http/routers/eda.py lines 1-95,
        transport/http/schemas/eda.py lines 1-72
  traps checked: 1 (seven paths match the pinned list),
                 2 (lint-imports clean; no integrations import),
                 4 (no-token test returns 401 WDK_LOGIN_REQUIRED),
                 8 (describe_study called from both the route and the tool)
```

A FAIL names the file, the line and the rule broken.

---

## Exit criteria

1. `cd apps/api && uv run ruff check src/ && uv run mypy --strict src/pathfinder/ && uv run pyright src/pathfinder/ && uv run lint-imports && uv run pytest src/pathfinder/tests/ -v` is green, run by the lead.
2. `cd apps/web && npx tsc --noEmit && npx eslint src/ && node scripts/check-boundaries.mjs && npx vitest run` is green, run by the lead.
3. `cd packages/shared-ts && yarn typecheck` is green (its lint is apps/web's
   eslint, already in criterion 2), and
   `cd packages/assistant-client-ts && yarn test && yarn typecheck && yarn lint`
   is green and unchanged by this batch.
4. The seven pinned routes exist with exactly those paths and methods, each one
   carries `require_registered_wdk_identity`, and the PATCH accepts exactly the
   five-member action union (`bind`, `set-filters`, `run-compute`,
   `export-step`, `unbind`) with the `{analysis, job, step}` response batch 5's
   client parses.
5. `packages/spec/openapi.json` carries `EdaAnalysisState`,
   `EdaSubsetPreviewPart` and `EdaVizPart` under `components.schemas`, and the
   regenerated `packages/shared-ts/src/generated/` is committed.
6. `packages/shared-ts/src/generated/zod/` holds the three EDA schemas, and no
   zod schema for an EDA part is hand-written.
7. `test_eda_kinds_match_shared_ts.py` passes in both directions.
8. `dataPartComponents` is total over `KnownDataPartKind` with no suppression,
   and the three renderers show real content rather than returning null.
9. `grep -rn "as any\|@ts-ignore\|@ts-expect-error\|eslint-disable" apps/web/src/features/conversation/content packages/shared-ts/src/types.ts`
   finds nothing new.
10. The verifier report is PASS on every task, with evidence lines, and the lead
    has spot-read `routers/eda.py`, `schemas/eda.py`, `types.ts` and the three
    components against this document.
11. Zero debt: no unused import, no field nothing reads, no route without a
    test, no TODO. The recap leads with that sentence or the batch stays open.
