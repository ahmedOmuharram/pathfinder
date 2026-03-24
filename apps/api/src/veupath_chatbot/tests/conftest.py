import asyncio
import contextlib
import os
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
import redis
import respx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

import veupath_chatbot.persistence.session as session_module
import veupath_chatbot.platform.redis as redis_module
import veupath_chatbot.services.chat.orchestrator as _orch
import veupath_chatbot.services.workbench_chat.orchestrator
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.main import create_app
from veupath_chatbot.persistence.models import Base, User
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.security import create_user_token, limiter
from veupath_chatbot.tests.fixtures.scripted_engine import (
    ScriptedKaniEngine,
    ScriptedTurn,
)


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
        "postgres:16-alpine",
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


@pytest.fixture(scope="session")
async def db_engine(
    database_url: str, postgres_container: PostgresContainer | None
) -> AsyncGenerator[AsyncEngine]:
    del postgres_container
    database_url = _get_test_database_url()
    # pytest-asyncio runs tests on different event loops. Asyncpg connections are bound
    # to the loop they were created in. Use NullPool to avoid cross-loop reuse.
    engine = create_async_engine(database_url, poolclass=NullPool)

    # Ensure tables exist once for the session.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

    :param db_engine: Database engine.
    :param session_maker: Async session maker.

    """
    session_module._state["engine"] = db_engine
    session_module._state["session_factory"] = session_maker


@pytest.fixture
async def db_cleaner(db_engine: AsyncEngine) -> AsyncGenerator[None]:
    yield
    # Drain lingering background chat tasks so their DB sessions
    # commit/close before TRUNCATE.  Without this, TRUNCATE deadlocks
    # against the background task's uncommitted writes.
    all_tasks = list(
        veupath_chatbot.services.chat.orchestrator._active_tasks.values()
    ) + list(
        veupath_chatbot.services.workbench_chat.orchestrator._active_tasks.values()
    )
    if all_tasks:
        _, pending = await asyncio.wait(all_tasks, timeout=5.0)
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    # Truncate after each test so request-level commits don't leak state.
    async with db_engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE TABLE "
            "operations, stream_projections, streams, "
            "experiments, gene_sets, control_sets, users "
            "RESTART IDENTITY CASCADE"
        )


# ---------------------------------------------------------------------------
# Redis — real instance, not fakeredis
# ---------------------------------------------------------------------------


def _probe_redis(url: str) -> bool:
    """Synchronously check if a Redis server is reachable."""
    try:
        r = redis.from_url(url, socket_connect_timeout=2)
        r.ping()
        r.close()
    except redis.ConnectionError, redis.TimeoutError, OSError:
        return False
    return True


@pytest.fixture(scope="session")
def redis_url() -> str:
    return os.environ.get("REDIS_URL", "").strip()


@pytest.fixture(scope="session")
def redis_container(redis_url: str) -> Generator[RedisContainer | None]:
    """Start a real Redis container if no REDIS_URL is set.

    Mirrors the PostgreSQL container pattern: prefer explicit env var,
    fall back to testcontainers.
    """
    url = redis_url or os.environ.get("REDIS_URL", "").strip()
    if url and _probe_redis(url):
        yield None
        return

    container = RedisContainer("redis:7-alpine")
    try:
        container.start()
    except Exception as exc:
        msg = (
            "REDIS_URL was not set and Redis could not be started via Docker. "
            "Fix by either:\n"
            "- setting REDIS_URL to a running Redis instance, or\n"
            "- installing/running Docker so testcontainers can start Redis.\n"
            f"Underlying error: {exc}"
        )
        raise RuntimeError(msg) from exc

    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    url = f"redis://{host}:{port}/0"
    os.environ["REDIS_URL"] = url
    yield container
    container.stop()


@pytest.fixture(scope="session")
def _get_test_redis_url(redis_container: RedisContainer | None) -> str:
    del redis_container
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


# ---------------------------------------------------------------------------
# Redis — session-scoped connection, per-test flush
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def _redis_conn(_get_test_redis_url: str) -> AsyncGenerator[Redis]:
    """One real Redis connection for the entire test session.

    Lazily started — the container only boots when a test actually needs Redis.
    """
    conn = Redis.from_url(_get_test_redis_url, decode_responses=False)
    await conn.ping()
    yield conn
    await conn.aclose()


@pytest.fixture
async def redis_setup(_redis_conn: Redis) -> AsyncGenerator[None]:
    """Opt-in fixture: makes Redis available and flushes between tests."""
    redis_module._state["redis"] = _redis_conn
    await _redis_conn.flushdb()
    return


# ---------------------------------------------------------------------------
# Environment + App
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _test_env_defaults() -> None:
    # Keep tests deterministic and avoid background ingestion/LLM calls.
    os.environ.setdefault("API_SECRET_KEY", "test-secret-key-test-secret-key-test")

    os.environ.setdefault("PATHFINDER_CHAT_PROVIDER", "mock")
    os.environ.setdefault("OPENAI_API_KEY", "")
    os.environ.setdefault("ANTHROPIC_API_KEY", "")
    os.environ.setdefault("GEMINI_API_KEY", "")

    # Disable rate limiting so chat tests don't get 429s.
    limiter.enabled = False


@pytest.fixture
def app() -> FastAPI:
    # Ensure settings reads current env, not cached values from prior imports.
    get_settings.cache_clear()

    # Reset orchestrator globals so _wire_ai_dependencies() starts clean.
    _orch._create_agent_holder.clear()
    _orch._resolve_model_id_holder.clear()
    _orch._mock_stream_fn = None

    return create_app()


@pytest.fixture
async def client(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    redis_setup: None,
) -> AsyncGenerator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as c:
        yield c


@pytest.fixture
async def authed_client(
    client: httpx.AsyncClient,
) -> AsyncGenerator[httpx.AsyncClient]:
    """
    Client with a valid `pathfinder-auth` cookie set (anonymous user created).
    """
    user_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    token = create_user_token(user_id)
    client.cookies.set("pathfinder-auth", token)
    return client


@pytest.fixture
def wdk_respx() -> Generator[respx.Router]:
    """respx router for mocking outbound WDK httpx requests.

    The WDK integration uses httpx.AsyncClient under the hood, so respx can
    intercept those requests by matching on full URLs.


    """
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture(autouse=True)
async def _close_wdk_clients_after_test() -> AsyncGenerator[None]:
    """Close shared WDK httpx clients after each test.

    The site_router caches httpx clients.  If we don't close them between
    tests, the next test may try to reuse connections from an event loop
    that asyncio has already torn down.
    """
    yield
    try:
        router = get_site_router()
        await router.close_all()
    except RuntimeError, OSError:
        pass  # Client already closed or event loop torn down


@pytest.fixture
def scripted_engine_factory() -> Callable[
    [list[ScriptedTurn]],
    contextlib.AbstractContextManager[ScriptedKaniEngine],
]:
    """Fixture that patches ``create_engine`` so Kani agents use a ScriptedKaniEngine.

    Returns a context-manager function.  Usage inside a test::

        with scripted_engine_factory(turns) as engine:
            # engine is the ScriptedKaniEngine; send chat requests here
            ...

    The mock-chat-provider env var is explicitly cleared so that the
    orchestrator uses the real ``stream_chat`` path (agent + tools + live WDK).


    """

    @contextmanager
    def _factory(
        turns: list[ScriptedTurn],
    ) -> Generator[ScriptedKaniEngine]:
        engine = ScriptedKaniEngine(turns)
        with (
            patch(
                "veupath_chatbot.ai.agents.factory.create_engine",
                return_value=engine,
            ),
            patch(
                "veupath_chatbot.services.chat.orchestrator._mock_stream_fn",
                None,
            ),
            patch.dict(
                os.environ,
                {"PATHFINDER_CHAT_PROVIDER": ""},
                clear=False,
            ),
        ):
            yield engine

    return _factory
