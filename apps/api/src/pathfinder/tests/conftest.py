import asyncio
import os
from collections.abc import AsyncGenerator, Coroutine, Generator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

# ---------------------------------------------------------------------------
# PIGuard ONNX model — MUST run before any pathfinder imports.
# ---------------------------------------------------------------------------
# SecurityGuardrail() is instantiated at agent module level, so the model
# must be available before the import chain reaches it.  huggingface_hub
# caches to ~/.cache/huggingface/hub/ — the network download only happens
# once per machine.

if "PIGUARD_MODEL_DIR" not in os.environ:
    from huggingface_hub import hf_hub_download

    _piguard_cache = Path.home() / ".cache" / "pathfinder" / "piguard"
    _piguard_cache.mkdir(parents=True, exist_ok=True)
    for _fname in ("model.onnx", "tokenizer.json"):
        hf_hub_download(
            repo_id="ahmedomuharram/piguard-onnx",
            filename=_fname,
            local_dir=str(_piguard_cache),
        )
    os.environ["PIGUARD_MODEL_DIR"] = str(_piguard_cache)

# ---------------------------------------------------------------------------

os.environ.setdefault("API_ENV", "test")
os.environ.setdefault("API_SECRET_KEY", "test-secret-key-test-secret-key-test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/pathfinder_test",
)
os.environ.setdefault("PATHFINDER_CHAT_PROVIDER", "mock")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("GEMINI_API_KEY", "")

import httpx
import procrastinate
import psycopg
import pydantic_ai.models
import pytest
from fastapi import FastAPI
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

import pathfinder.persistence.session as session_module
from pathfinder.ai.conversation.checkpointer import to_psycopg_url
from pathfinder.integrations.veupathdb.site_router import get_site_router
from pathfinder.jobs.app import procrastinate_app
from pathfinder.main import create_app
from pathfinder.persistence.models import Base, User
from pathfinder.platform.config import get_settings
from pathfinder.platform.security import create_user_token, limiter

# Block real LLM calls in all tests — use TestModel/FunctionModel instead.
pydantic_ai.models.ALLOW_MODEL_REQUESTS = False


async def _probe_connection(url: str) -> bool:
    """Try connecting to the given URL. Returns False if role does not exist."""
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as _:
            pass
    except Exception as e:
        err = str(e).lower()
        if "does not exist" in err and "role" in err:
            return False
        raise
    else:
        return True
    finally:
        await engine.dispose()


def _get_test_database_url() -> str:
    url = (
        os.environ.get("DATABASE_URL")
        or "postgresql+asyncpg://postgres:postgres@localhost:5432/pathfinder_test"
    )
    if not url.startswith("postgresql"):
        msg = f"Tests require PostgreSQL DATABASE_URL, got: {url!r}."
        raise RuntimeError(msg)

    # Safety: refuse to run against a non-test DB unless explicitly overridden.
    allow = os.environ.get("ALLOW_NONTEST_DATABASE") == "1"
    if not allow and "pathfinder_test" not in url:
        msg = (
            "Refusing to run tests against a non-test database. "
            "Set DATABASE_URL to a test DB (suggested db name: 'pathfinder_test'), "
            "or set ALLOW_NONTEST_DATABASE=1 to override."
        )
        raise RuntimeError(msg)
    return url


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def database_url() -> str:
    # Prefer explicit env var. If absent, we will start a disposable Postgres below.
    return os.environ.get("DATABASE_URL", "").strip()


@pytest.fixture(scope="session")
def postgres_container(
    database_url: str,
) -> Generator[PostgresContainer | None]:
    url = database_url or os.environ.get("DATABASE_URL", "").strip()
    if url and "postgresql" in url:
        # Validate connection. On macOS, localhost:5432 may point to Homebrew
        # Postgres which uses the system user, not "postgres".
        # Connection refused / timeout / OS errors propagate so the user
        # can fix DATABASE_URL or start Postgres.
        parsed = make_url(url)
        probe_url = (
            str(
                parsed.set(drivername="postgresql+asyncpg").render_as_string(
                    hide_password=False
                )
            )
            if "asyncpg" not in (parsed.drivername or "")
            else url
        )
        if not asyncio.run(_probe_connection(probe_url)):
            url = ""
            os.environ.pop("DATABASE_URL", None)

    if url:
        yield None
        return

    # This requires Docker
    container = PostgresContainer(
        "pgvector/pgvector:pg16",
        username="postgres",
        password="postgres",
        dbname="pathfinder_test",
    )
    try:
        container.start()
    except Exception as exc:
        msg = (
            "DATABASE_URL was not set and Postgres could not be started via Docker. "
            "Fix by either:\n"
            "- setting DATABASE_URL to a test database URL, or\n"
            "- installing/running Docker so testcontainers can start Postgres.\n"
            f"Underlying error: {exc}"
        )
        raise RuntimeError(msg) from exc

    # Convert the container URL to asyncpg for SQLAlchemy async engine.
    url_obj = make_url(container.get_connection_url()).set(
        drivername="postgresql+asyncpg"
    )
    os.environ["DATABASE_URL"] = url_obj.render_as_string(hide_password=False)
    yield container
    container.stop()


_PROCRASTINATE_SCHEMA_SQL = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "procrastinate_schema.sql"
).read_text()


def _apply_procrastinate_schema_sync(database_url: str) -> None:
    """Apply the Procrastinate schema via psycopg.

    Asyncpg rejects multi-statement SQL inside a single prepared statement, so
    the procrastinate DDL (which contains ~600 lines of CREATE FUNCTION /
    CREATE TRIGGER blocks) must be applied through a driver that accepts it.
    Psycopg happily executes multi-statement strings. We only apply when the
    target tables are missing so the call is idempotent across test sessions.
    """
    psycopg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(psycopg_url, autocommit=True) as connection, \
            connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'procrastinate_jobs'"
        )
        if cursor.fetchone() is not None:
            return
        cursor.execute(_PROCRASTINATE_SCHEMA_SQL)


@pytest.fixture(scope="session")
async def db_engine(
    database_url: str, postgres_container: PostgresContainer | None
) -> AsyncGenerator[AsyncEngine]:
    del postgres_container
    database_url = _get_test_database_url()
    # pytest-asyncio runs tests on different event loops. Asyncpg connections are bound
    # to the loop they were created in. Use NullPool to avoid cross-loop reuse.
    engine = create_async_engine(database_url, poolclass=NullPool)

    # Ensure pgvector extension + tables exist once for the session.
    async with engine.begin() as conn:
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.run_sync(Base.metadata.create_all)

    # Procrastinate's DDL is multi-statement and asyncpg rejects that inside
    # prepared statements. Apply via psycopg (same driver Alembic uses).
    _apply_procrastinate_schema_sync(database_url)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def session_maker(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture(scope="session")
def patch_app_db_engine(
    db_engine: AsyncEngine, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    """Patch the app's global DB engine/sessionmaker so:
    - FastAPI lifespan init_db() uses the test engine
    - get_db_session dependency uses the test engine
    - the module-level Procrastinate connector points at the test DB

    The last point matters because ``pathfinder.jobs.app`` builds a
    ``PsycopgConnector`` at import time using ``get_settings().database_url``.
    When a test uses ``testcontainers``, the DB URL is assigned to
    ``os.environ["DATABASE_URL"]`` *after* that import happens, so we must
    rebuild the connector once the test DB is known.

    :param db_engine: Database engine.
    :param session_maker: Async session maker.

    """
    session_module._engine = db_engine
    session_module._session_factory_instance = session_maker

    get_settings.cache_clear()
    test_connector = procrastinate.PsycopgConnector(
        conninfo=to_psycopg_url(get_settings().database_url),
    )
    procrastinate_app.connector = test_connector
    procrastinate_app.job_manager.connector = test_connector


@pytest.fixture
async def db_cleaner(db_engine: AsyncEngine) -> AsyncGenerator[None]:
    yield
    # New chat dispatcher is single-request (no background tasks to drain).
    # Truncate after each test so request-level commits don't leak state.
    async with db_engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE TABLE "
            "messages, conversations, exports, "
            "experiments, gene_sets, control_sets, users "
            "RESTART IDENTITY CASCADE"
        )


# ---------------------------------------------------------------------------
# Environment + App
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _test_env_defaults() -> None:
    # Keep tests deterministic and avoid background ingestion/LLM calls.
    # Disable rate limiting so chat tests don't get 429s.
    limiter.enabled = False


@pytest.fixture
def app() -> FastAPI:
    # Ensure settings reads current env, not cached values from prior imports.
    get_settings.cache_clear()
    return create_app()


@pytest.fixture
async def client(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
) -> AsyncGenerator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as c:
        yield c


@pytest.fixture
async def authed_user_id(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> UUID:
    """
    Create an anonymous user row and return its id.

    Shares the user row with ``authed_client``; tests needing only the id
    (e.g. direct store calls) depend on this fixture, while tests needing
    an HTTP client depend on ``authed_client``.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()
    return user_id


@pytest.fixture
async def authed_client(
    client: httpx.AsyncClient,
    authed_user_id: UUID,
) -> httpx.AsyncClient:
    """Client with a valid `pathfinder-auth` cookie set."""
    token = create_user_token(authed_user_id)
    client.cookies.set("pathfinder-auth", token)
    return client


@pytest.fixture
async def app_notify_dispatcher(
    app: FastAPI,
    patch_app_db_engine: None,
) -> AsyncGenerator[Any]:
    """Attach a running :class:`NotifyDispatcher` to ``app.state``.

    Tests that hit the task-events SSE endpoint need this — production
    ``main.py`` lifespan opens the dispatcher, but the ASGI test transport
    skips lifespan.
    """
    del patch_app_db_engine
    from pathfinder.platform.notify_dispatcher import (  # noqa: PLC0415
        lifespan_notify_dispatcher,
    )
    database_url = os.environ["DATABASE_URL"]
    async with lifespan_notify_dispatcher(database_url) as dispatcher:
        app.state.notify_dispatcher = dispatcher
        yield dispatcher


@pytest.fixture
async def app_memory_store(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
) -> AsyncGenerator[Any]:
    """Open a `MemoryStore` bound to the test DB and attach it to `app.state`.

    The production `main.py` lifespan does this attachment; tests skip the
    FastAPI lifespan (ASGITransport mounts the app without running startup),
    so we do it explicitly here. We also open a
    :class:`NotifyDispatcher` so endpoints that subscribe via
    ``app.state.notify_dispatcher`` see a functioning multiplexer.
    """
    del patch_app_db_engine, db_cleaner
    from pathfinder.ai.memory.lifespan import (  # noqa: PLC0415
        lifespan_memory_store,
    )
    from pathfinder.ai.memory.store import MemoryStore  # noqa: PLC0415
    from pathfinder.platform.notify_dispatcher import (  # noqa: PLC0415
        lifespan_notify_dispatcher,
    )

    database_url = os.environ["DATABASE_URL"]
    async with (
        lifespan_memory_store(database_url) as raw,
        lifespan_notify_dispatcher(database_url) as disp,
    ):
        store = MemoryStore(store=raw)
        app.state.memory_store = raw
        app.state.notify_dispatcher = disp
        yield store


@pytest.fixture(autouse=True)
async def _close_wdk_clients_after_test() -> AsyncGenerator[None]:
    """Close shared WDK clients and clear discovery cache after each test.

    The site_router caches httpx clients and the DiscoveryService caches
    catalogs.  Clearing both between tests prevents cross-test state
    leakage — stale catalogs causing apparent test isolation failures,
    or closed clients being reused by later tests.
    """
    from pathfinder.integrations.veupathdb.discovery_service import (  # noqa: PLC0415
        _discovery_holder,
    )

    _discovery_holder.clear()

    yield
    try:
        router = get_site_router()
        await router.close_all()
    except RuntimeError, OSError:
        pass  # Client already closed or event loop torn down


# ---------------------------------------------------------------------------
# Background task control
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _eager_spawn(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    """Replace spawn() with a tracked version that awaits all tasks in teardown.

    Real ``spawn()`` creates fire-and-forget background tasks.  In tests,
    these can outlive the test, hit closed DB connections, or make
    unexpected WDK calls.  This fixture creates real ``asyncio.Task``
    objects (so background logic actually runs) but tracks them and awaits
    completion in teardown before ``db_cleaner`` runs TRUNCATE.

    Autouse: every test gets this automatically.  No more per-test
    ``@patch("...spawn")`` decorators needed.
    """
    pending: set[asyncio.Task[Any]] = set()

    def _tracked_spawn(
        coro: Coroutine[Any, Any, Any], *, name: str | None = None
    ) -> asyncio.Task[Any] | None:
        try:
            task = asyncio.create_task(coro, name=name)
        except RuntimeError:
            coro.close()
            return None
        pending.add(task)
        task.add_done_callback(pending.discard)
        return task

    # spawn is imported by name in multiple modules — patch all binding sites
    monkeypatch.setattr("pathfinder.platform.tasks.spawn", _tracked_spawn)
    monkeypatch.setattr("pathfinder.platform.store.spawn", _tracked_spawn)

    yield

    # Await all spawned tasks before test teardown
    if pending:
        _done, timed_out = await asyncio.wait(pending, timeout=10.0)
        for t in timed_out:
            t.cancel()
        if timed_out:
            await asyncio.gather(*timed_out, return_exceptions=True)
