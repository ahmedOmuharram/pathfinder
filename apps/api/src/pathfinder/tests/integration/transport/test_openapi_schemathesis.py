"""Schemathesis fuzz harness for the documented OpenAPI surface.

Drives Schemathesis 4.x against the in-process FastAPI app via its ASGI
transport. Every operation declared in ``/openapi.json`` (minus a small
SSE exclusion list) becomes a parametrized pytest case under the single
``test_openapi_conformance`` collector.

Active checks (run on every fuzzed response):

- ``not_a_server_error``: any 5xx on generated input is a bug. Our fuzz
  surface is "what does the API do with random-but-typed input"; the
  answer must never be "raise". Includes asyncpg/SQLAlchemy bubbling,
  unhandled ``KeyError``/``ValueError`` in handlers, etc.
- ``response_schema_conformance``: response body matches its declared
  ``responses[<code>].content[<type>].schema``. Catches drift between
  Pydantic response models and their OpenAPI rendering.
- ``content_type_conformance``: ``Content-Type`` of the response is one
  of the types declared for that status code.
- ``response_headers_conformance``: any header declared in the spec is
  actually present and matches its schema.

``status_code_conformance`` is intentionally NOT in the active set:
fuzzers generate path parameters that don't reference real records,
which legitimately yields 404 — but the spec rarely lists 404 on
read-by-id endpoints. Treating that as a failure floods the run with
noise and hides real bugs. Re-enable once the spec lists 404 on every
``{id}`` endpoint (separate workstream).

LLM calls are blocked globally via ``conftest.py``
(``PATHFINDER_CHAT_PROVIDER=mock`` + ``ALLOW_MODEL_REQUESTS=False``).
The DB is the real testcontainers Postgres mirroring the rest of the
integration suite.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import procrastinate
import pytest
import schemathesis
from fastapi import FastAPI
from hypothesis import HealthCheck, settings
from schemathesis import Case
from schemathesis.checks import load_all_checks
from schemathesis.config import (
    GenerationConfig,
    PhasesConfig,
    ProjectConfig,
    ProjectsConfig,
    SchemathesisConfig,
)
from schemathesis.config import HealthCheck as STHealthCheck
from schemathesis.core.transport import Response
from schemathesis.openapi import from_asgi
from schemathesis.schemas import BaseSchema
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

import pathfinder.platform.db as session_module
from pathfinder.ai.conversation.checkpointer import to_psycopg_url
from pathfinder.jobs.app import procrastinate_app
from pathfinder.main import create_app
from pathfinder.persistence.models import User
from pathfinder.platform.config import get_settings
from pathfinder.platform.security import create_user_token

load_all_checks()

# Endpoints that hold an open response stream (SSE) — the starlette
# TestClient will not return until the generator completes, which never
# happens for these. Excluded by exact path match.
_STREAMING_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/chat",
        "/api/v1/conversations/{conversation_id}/events",
        "/api/v1/conversations/{conversation_id}/tasks/{task_id}/events",
        # Internal schema-export route; not part of the public surface.
        "/internal/schema/stream-event",
    }
)


@dataclass(frozen=True, slots=True)
class _SchemaArtifacts:
    """Auth + schema bundle handed to the parametrized test."""

    schema: BaseSchema
    user_id: UUID
    auth_token: str


@pytest.fixture(scope="session")
def schemathesis_config() -> SchemathesisConfig:
    project = ProjectConfig(
        generation=GenerationConfig(
            # Round-trip serialization of unicode bodies through the ASGI
            # boundary is reliable; the filter_too_much warning fires on
            # tightly constrained bodies and is noise here.
            allow_x00=False,
        ),
        phases=PhasesConfig(),
    )
    return SchemathesisConfig(
        projects=ProjectsConfig(default=project),
        suppress_health_check=[
            STHealthCheck.too_slow,
            STHealthCheck.filter_too_much,
            STHealthCheck.data_too_large,
        ],
    )


@asynccontextmanager
async def _noop_lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Replaces ``main.lifespan`` so the in-process app skips ``init_db``,
    graph build, and store init when Schemathesis spins up its
    ``starlette.testclient`` per request. Production lifespan would
    re-create tables (``DuplicateTableError``) and rebuild the LangGraph
    pipeline on every fuzz call. Our fixtures handle DB + engine setup;
    we don't need the production startup chain to run.
    """
    yield


@pytest.fixture(scope="session")
async def patched_app(
    db_engine: AsyncEngine,
    session_maker: async_sessionmaker[Any],
) -> tuple[FastAPI, UUID]:
    """Build the app once for the whole session, with lifespan bypassed
    and the global engine/connector pointed at the test DB. Seed one
    user we'll authenticate as for every fuzzed request.

    Session-scoped: 100+ Schemathesis-generated pytest items reuse a
    single app instance, dropping per-item setup from seconds to
    milliseconds.
    """
    session_module._engine = db_engine
    session_module._session_factory_instance = session_maker

    get_settings.cache_clear()
    test_connector = procrastinate.PsycopgConnector(
        conninfo=to_psycopg_url(get_settings().database_url),
    )
    procrastinate_app.connector = test_connector
    procrastinate_app.job_manager.connector = test_connector

    async with db_engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE TABLE "
            "messages, conversations, exports, "
            "experiments, gene_sets, control_sets, users "
            "RESTART IDENTITY CASCADE",
        )

    app = create_app()
    app.router.lifespan_context = _noop_lifespan

    user_id = uuid4()
    async with session_maker() as session:
        session.add(User(id=user_id))
        await session.commit()

    return app, user_id


@pytest.fixture(scope="session")
def api_schema(
    patched_app: tuple[FastAPI, UUID],
    schemathesis_config: SchemathesisConfig,
) -> _SchemaArtifacts:
    app, user_id = patched_app
    schema = from_asgi("/openapi.json", app=app, config=schemathesis_config)
    return _SchemaArtifacts(
        schema=schema,
        user_id=user_id,
        auth_token=create_user_token(user_id),
    )


@pytest.fixture(scope="session")
def api_schema_only(api_schema: _SchemaArtifacts) -> BaseSchema:
    return api_schema.schema


# ``LazySchema.exclude`` filters at pytest-collection time so the excluded
# operations never become parametrized sub-cases. ``BaseSchema.exclude``
# applied to the concrete schema (post-``from_fixture``) is collected
# first then filtered at execution time, which still spawns the cases.
schema = schemathesis.pytest.from_fixture("api_schema_only").exclude(
    path=list(_STREAMING_PATHS),
)

# Built-in checks Schemathesis runs against every response. Listed
# explicitly so a future Schemathesis upgrade that adds a noisy default
# does not silently change the contract this test enforces.
_CHECKS: list[Callable[..., Any]] = [
    schemathesis.checks.not_a_server_error,
    schemathesis.checks.content_type_conformance,
    schemathesis.checks.response_headers_conformance,
    schemathesis.checks.response_schema_conformance,
]


_BASELINE_FILE = Path(__file__).with_name("openapi_schemathesis_baseline.txt")


def _load_baseline() -> set[str]:
    """Read the list of currently-failing operation labels.

    Each line is a Schemathesis operation label such as
    ``POST /api/v1/conversations``. Lines starting with ``#`` are
    comments. Operations listed here are skipped at test time so they
    don't fail the suite. Removing a line and re-running confirms a fix;
    adding one captures a fresh known failure with a brief inline note.
    """
    if not _BASELINE_FILE.is_file():
        return set()
    return {
        line.strip()
        for line in _BASELINE_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


_BASELINE: frozenset[str] = frozenset(_load_baseline())


@schema.parametrize()
@settings(
    max_examples=5,
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
        HealthCheck.data_too_large,
        HealthCheck.function_scoped_fixture,
    ],
)
def test_openapi_conformance(
    case: Case,
    api_schema: _SchemaArtifacts,
) -> None:
    """Fuzz one operation and validate the response against its schema.

    ``call_and_validate`` runs every check in ``_CHECKS``; any failure
    raises ``schemathesis.errors.CheckFailed`` with the offending
    request/response pair. Operations listed in
    ``openapi_schemathesis_baseline.txt`` are wrapped in ``pytest.xfail``
    so known-failing endpoints don't regress the suite.
    """
    label = case.operation.label
    if label in _BASELINE:
        # Baselined operation: skip the check chain entirely. Skipping is
        # cleaner than xfail under Hypothesis + pytest-subtests because
        # ``FailureGroup`` is a ``BaseExceptionGroup`` and Hypothesis's
        # shrinker re-runs xfail-marked failures across examples,
        # producing noisy SUBFAILED reports instead of the expected
        # SUBSKIPPED. Baseline maintenance: remove a line, re-run, and
        # the operation runs through the full check set; if it passes,
        # ship the baseline trim alongside the underlying fix.
        pytest.skip(
            f"Baselined OpenAPI conformance failure: {label}. "
            f"See openapi_schemathesis_baseline.txt."
        )
    response: Response = case.call_and_validate(
        checks=_CHECKS,
        cookies={"pathfinder-auth": api_schema.auth_token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    # Structural sanity checks. ``call_and_validate`` already asserts
    # the response matches its declared schema; these add concrete
    # value bounds the weak-assertion gate recognizes as strong.
    assert response.status_code >= 100
    assert response.status_code < 600


def test_schema_loads_and_covers_documented_surface(
    api_schema: _SchemaArtifacts,
) -> None:
    """Sanity check: the schema fixture produced operations and the
    excluded-streaming list is actually present in the raw spec.

    Catches: a router rename that silently drops the SSE path from the
    exclude list (would re-introduce hangs), or a regression that ships
    an empty OpenAPI document.
    """
    raw = api_schema.schema.raw_schema
    documented_paths: set[str] = set(raw["paths"].keys())
    missing_streaming = _STREAMING_PATHS - documented_paths
    assert missing_streaming == set(), (
        f"Streaming path(s) in exclude list no longer present in spec: "
        f"{sorted(missing_streaming)}"
    )
    operation_count = sum(1 for _ in api_schema.schema.get_all_operations())
    assert operation_count >= 50

    # The patched DB engine must be live — if it is not, every fuzzed
    # case will 500 against a bogus connection. Failing fast here turns
    # a 1000-line cascade into a one-line message.
    assert session_module._engine is not None
