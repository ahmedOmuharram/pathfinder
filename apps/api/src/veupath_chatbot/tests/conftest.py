import asyncio
import contextlib
import os
from collections.abc import AsyncGenerator, Callable, Generator
from uuid import uuid4

import httpx
import pytest
import respx
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
        return True
    except Exception as e:
        err = str(e).lower()
        if "does not exist" in err and "role" in err:
            return False
        raise
    finally:
        await engine.dispose()


def _get_test_database_url() -> str:
    url = (
        os.environ.get("DATABASE_URL")
        or "postgresql+asyncpg://postgres:postgres@localhost:5432/pathfinder_test"
    )
    if not url.startswith("postgresql"):
        raise RuntimeError(f"Tests require PostgreSQL DATABASE_URL, got: {url!r}.")

    # Safety: refuse to run against a non-test DB unless explicitly overridden.
    allow = os.environ.get("ALLOW_NONTEST_DATABASE") == "1"
    if not allow and "pathfinder_test" not in url:
        raise RuntimeError(
            "Refusing to run tests against a non-test database. "
            "Set DATABASE_URL to a test DB (suggested db name: 'pathfinder_test'), "
            "or set ALLOW_NONTEST_DATABASE=1 to override."
        )
    return url


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
        try:
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
        except Exception:
            # Connection refused, timeout, etc. Re-raise so user fixes
            # DATABASE_URL or starts their Postgres.
            raise

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
        raise RuntimeError(
            "DATABASE_URL was not set and Postgres could not be started via Docker. "
            "Fix by either:\n"
            "- setting DATABASE_URL to a test database URL, or\n"
            "- installing/running Docker so testcontainers can start Postgres.\n"
            f"Underlying error: {exc}"
        ) from exc

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
    from veupath_chatbot.persistence.models import Base

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
    import veupath_chatbot.persistence.session as session_module

    session_module.engine = db_engine
    session_module.async_session_factory = session_maker


@pytest.fixture
async def db_cleaner(db_engine: AsyncEngine) -> AsyncGenerator[None]:
    yield
    # Truncate after each test so request-level commits don't leak state.
    async with db_engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE TABLE "
            "strategy_history, strategies, plan_sessions, users "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture(scope="session", autouse=True)
def _test_env_defaults() -> None:
    # Keep tests deterministic and avoid background ingestion/LLM calls.
    os.environ.setdefault("API_SECRET_KEY", "test-secret-key-test-secret-key-test")
    os.environ.setdefault("RAG_ENABLED", "false")
    os.environ.setdefault("OPENAI_API_KEY", "")
    os.environ.setdefault("ANTHROPIC_API_KEY", "")
    os.environ.setdefault("GEMINI_API_KEY", "")


@pytest.fixture
def app() -> FastAPI:
    # Ensure settings reads current env, not cached values from prior imports.
    from veupath_chatbot.platform.config import get_settings

    get_settings.cache_clear()

    from veupath_chatbot.main import create_app

    return create_app()


@pytest.fixture
async def client(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
) -> AsyncGenerator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def authed_client(
    client: httpx.AsyncClient,
) -> AsyncGenerator[httpx.AsyncClient]:
    """
    Client with a valid `pathfinder-auth` cookie set (anonymous user created).
    """
    import veupath_chatbot.persistence.session as session_module
    from veupath_chatbot.persistence.models import User
    from veupath_chatbot.platform.security import create_user_token

    user_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    token = create_user_token(user_id)
    client.cookies.set("pathfinder-auth", token)
    yield client


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
        from veupath_chatbot.integrations.veupathdb.site_router import get_site_router

        router = get_site_router()
        await router.close_all()
    except Exception:
        pass


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
    from contextlib import contextmanager
    from unittest.mock import patch

    @contextmanager
    def _factory(
        turns: list[ScriptedTurn],
    ) -> Generator[ScriptedKaniEngine]:
        engine = ScriptedKaniEngine(turns)
        with (
            patch(
                "veupath_chatbot.ai.agent_factory.create_engine",
                return_value=engine,
            ),
            patch.dict(
                os.environ,
                {"PATHFINDER_CHAT_PROVIDER": ""},
                clear=False,
            ),
        ):
            yield engine

    return _factory
