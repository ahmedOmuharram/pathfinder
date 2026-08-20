import asyncio
import os
from collections.abc import AsyncGenerator, Coroutine, Generator
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

# The scanner is built at module import, so the PIGuard model must be on disk
# before the first pathfinder import.

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

# The default fastembed cache is a temporary directory that can disappear
# during a download, so tests use a durable one.
os.environ.setdefault(
    "FASTEMBED_CACHE_DIR",
    str(Path.home() / ".cache" / "pathfinder" / "fastembed"),
)

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
from fastapi import Depends, FastAPI
from procrastinate.testing import InMemoryConnector
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

import pathfinder.platform.db as session_module
from pathfinder.ai.conversation.checkpointer import to_psycopg_url
from pathfinder.integrations.veupathdb.site_router import get_site_router
from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.tasks import ensure_registered
from pathfinder.main import create_app
from pathfinder.persistence.models import Base, User
from pathfinder.platform.config import get_settings
from pathfinder.platform.security import create_user_token, limiter
from pathfinder.tests._support.wdk_credentials import (
    NO_CREDENTIALS_REASON,
    registered_wdk_token,
)
from pathfinder.transport.http.deps import (
    get_current_user_with_db_row,
    require_registered_wdk_identity,
)

# A test must never send a request to a real model.
pydantic_ai.models.ALLOW_MODEL_REQUESTS = False


async def _probe_connection(url: str) -> bool:
    """Returns False when the database role does not exist."""
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

    # Tests refuse to run against a database that is not a test database.
    allow = os.environ.get("ALLOW_NONTEST_DATABASE") == "1"
    if not allow and "pathfinder_test" not in url:
        msg = (
            "Refusing to run tests against a non-test database. "
            "Set DATABASE_URL to a test DB (suggested db name: 'pathfinder_test'), "
            "or set ALLOW_NONTEST_DATABASE=1 to override."
        )
        raise RuntimeError(msg)
    return url


# PostgreSQL.


@pytest.fixture(scope="session")
def database_url() -> str:
    # An empty result makes the session start a disposable Postgres.
    return os.environ.get("DATABASE_URL", "").strip()


@pytest.fixture(scope="session")
def postgres_container(
    database_url: str,
) -> Generator[PostgresContainer | None]:
    url = database_url or os.environ.get("DATABASE_URL", "").strip()
    if url and "postgresql" in url:
        # A local Postgres can lack the configured role, so probe it first.
        # Every other connection error propagates.
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
    """Applies the Procrastinate schema through psycopg.

    Asyncpg rejects multi-statement SQL, and this schema is multi-statement.
    The call is idempotent, because it runs only when the tables are absent.
    """
    psycopg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    with (
        psycopg.connect(psycopg_url, autocommit=True) as connection,
        connection.cursor() as cursor,
    ):
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
    # An asyncpg connection belongs to the event loop that created it, and
    # tests run on different loops. NullPool prevents reuse across loops.
    engine = create_async_engine(database_url, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.run_sync(Base.metadata.create_all)

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
    """Points the global engine, session maker and job connector at the test database.

    The job connector is built at import time, which can happen before the
    test database is known, so this rebuilds it.
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
    # Truncate after each test so committed rows do not leak into the next one.
    async with db_engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE TABLE "
            "messages, conversations, exports, "
            "experiments, gene_sets, control_sets, users "
            "RESTART IDENTITY CASCADE"
        )
        # The store tables exist only after a memory test creates them.
        await conn.exec_driver_sql(
            "DO $$ BEGIN "
            "IF to_regclass('public.store') IS NOT NULL THEN "
            "TRUNCATE TABLE store, store_vectors RESTART IDENTITY CASCADE; "
            "END IF; END $$"
        )


@pytest.fixture
async def in_memory_jobs() -> AsyncGenerator[InMemoryConnector]:
    """Route deferred jobs to an in-memory connector, so a test decides when
    a job runs. The teardown restores the original connector.
    """
    original_connector = procrastinate_app.connector
    original_jm_connector = procrastinate_app.job_manager.connector
    connector = InMemoryConnector()
    procrastinate_app.connector = connector
    procrastinate_app.job_manager.connector = connector
    ensure_registered()
    try:
        yield connector
    finally:
        procrastinate_app.connector = original_connector
        procrastinate_app.job_manager.connector = original_jm_connector


# Environment and app.


@pytest.fixture(scope="session", autouse=True)
def _test_env_defaults() -> None:
    # The rate limiter stays off, because a test can exceed the request rate.
    limiter.enabled = False


@pytest.fixture
def app() -> FastAPI:
    # Settings must read the current environment, not a cached value.
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
    """Creates an anonymous user row and returns its id.

    The authenticated client fixture shares this user row.
    """
    del patch_app_db_engine, db_cleaner
    user_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()
    return user_id


@pytest.fixture
def signed_in_to_veupathdb(app: FastAPI) -> Generator[None]:
    """Let the WDK-backed routes run as a user who holds a VEuPathDB session.

    The gate itself is covered by ``test_wdk_login_required``; a suite about
    what a route does once past it states that it is past it.
    """

    async def _identity(
        user_id: Annotated[UUID, Depends(get_current_user_with_db_row)],
    ) -> UUID:
        return user_id

    app.dependency_overrides[require_registered_wdk_identity] = _identity
    yield
    app.dependency_overrides.pop(require_registered_wdk_identity, None)


@pytest.fixture
async def authed_client(
    client: httpx.AsyncClient,
    authed_user_id: UUID,
    signed_in_to_veupathdb: None,
) -> httpx.AsyncClient:
    """Returns a client that carries a valid authentication cookie."""
    del signed_in_to_veupathdb
    token = create_user_token(authed_user_id)
    client.cookies.set("pathfinder-auth", token)
    return client


@pytest.fixture
async def app_notify_dispatcher(
    app: FastAPI,
    patch_app_db_engine: None,
) -> AsyncGenerator[Any]:
    """Attaches a running notify dispatcher to the application state.

    The test transport skips the lifespan that normally opens it.
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
    """Attaches a memory store and a notify dispatcher to the application state.

    The test transport skips the lifespan that normally opens them.
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


@pytest.fixture(scope="session")
async def wdk_registered_token() -> str | None:
    """The WDK token of the registered test account, or None when unconfigured.

    Resolved once for the whole session.
    """
    return await registered_wdk_token()


@pytest.fixture
def require_wdk_creds(wdk_registered_token: str | None) -> str:
    """The registered WDK token, or a skip naming the credentials to set."""
    if wdk_registered_token is None:
        pytest.skip(NO_CREDENTIALS_REASON)
    return wdk_registered_token


@pytest.fixture(autouse=True)
async def _close_wdk_clients_after_test() -> AsyncGenerator[None]:
    """Closes the shared WDK clients and clears the discovery cache after a test.

    Both are process-wide caches, so a test must not inherit them.
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
        pass  # The client is closed or the event loop is gone.


# Background task control.


@pytest.fixture(autouse=True)
async def _eager_spawn(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    """Tracks every spawned task and awaits it during teardown.

    The tasks still run, but none of them outlives the test that started it.
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

    # Several modules import spawn by name, so patch every binding site.
    monkeypatch.setattr("pathfinder.platform.tasks.spawn", _tracked_spawn)
    monkeypatch.setattr("pathfinder.platform.store.spawn", _tracked_spawn)

    yield

    if pending:
        _done, timed_out = await asyncio.wait(pending, timeout=10.0)
        for t in timed_out:
            t.cancel()
        if timed_out:
            await asyncio.gather(*timed_out, return_exceptions=True)
