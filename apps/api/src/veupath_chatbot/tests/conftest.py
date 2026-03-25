import asyncio
import contextlib
import hashlib
import json
import os
import re
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from contextlib import contextmanager
from typing import Any
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
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKIdentifier,
    WDKSearchConfig,
    WDKStepTree,
)
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
    """Close shared WDK clients and clear discovery cache after each test.

    The site_router caches httpx clients and the DiscoveryService caches
    catalogs.  Without clearing both, VCR cassettes become incomplete:
    test B reuses test A's cached catalog (no HTTP request recorded),
    so test B's cassette lacks the catalog request and replay fails.
    """
    # Clear discovery cache BEFORE the test so each test starts fresh
    # and records ALL its HTTP interactions into its own cassette.
    from veupath_chatbot.integrations.veupathdb.discovery import (  # noqa: PLC0415
        _discovery_holder,
    )

    _discovery_holder.clear()

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


# ---------------------------------------------------------------------------
# VCR cassette configuration
# ---------------------------------------------------------------------------
# Approach (per https://imoskvin.com/blog/redacting-vcrpy-cassettes/):
#
# 1. Redact PII fields (email, name, org) from response bodies.
# 2. Scrub auth cookies/headers.
# 3. Leave IDs (user IDs, step IDs) UNTOUCHED — they are internal WDK
#    identifiers (not PII) and are required for cassette replay matching.
# 4. Trim large arrays to reduce cassette size.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Deterministic ID anonymization
# ---------------------------------------------------------------------------
# Real WDK user IDs are hashed to stable fakes so cassettes don't leak
# account identifiers while preserving referential integrity (same real ID
# always maps to the same fake).  Custom VCR matchers apply the same hash
# so live requests match cassette entries during replay.

_USER_PATH_RE = re.compile(r"/users/(\d+)")
_HASHED_PREFIX = "999"


def _hash_uid(real_id: str) -> str:
    """Deterministic numeric fake from a real WDK user ID.

    Idempotent: IDs already starting with ``999`` (previously hashed)
    are returned as-is.
    """
    if real_id.startswith(_HASHED_PREFIX):
        return real_id
    h = int(hashlib.sha256(real_id.encode()).hexdigest()[:7], 16)
    return f"{_HASHED_PREFIX}{h}"


def _replace_user_ids(text: str) -> str:
    """Replace ``/users/{real_id}`` with ``/users/{hash}`` everywhere in *text*."""
    return _USER_PATH_RE.sub(lambda m: f"/users/{_hash_uid(m.group(1))}", text)

# PII fields in /users/current and profile JSON response bodies.
_PII_PATTERNS: list[tuple[str, str]] = [
    (r'"email"\s*:\s*"[^"]*"', '"email":"test@test.local"'),
    (r'"firstName"\s*:\s*"[^"]*"', '"firstName":"Test"'),
    (r'"lastName"\s*:\s*"[^"]*"', '"lastName":"User"'),
    (r'"middleName"\s*:\s*"[^"]*"', '"middleName":""'),
    (r'"username"\s*:\s*"[^"]*"', '"username":"test-user"'),
    (r'"organization"\s*:\s*"[^"]*"', '"organization":"Test Org"'),
    (r'"groupName"\s*:\s*"[^"]*"', '"groupName":"Test Group"'),
    (r'"groupType"\s*:\s*"[^"]*"', '"groupType":"research"'),
    (r'"position"\s*:\s*"[^"]*"', '"position":"researcher"'),
    (r'"interests"\s*:\s*"[^"]*"', '"interests":""'),
]

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SAFE_EMAILS = frozenset({"test@test.local", "scrubbed@test.local"})
_COOKIE_SCRUB_RE = re.compile(r"(Authorization|JSESSIONID|wdk_check_auth)=[^;]+")

_TRIM_THRESHOLD = 50_000  # Only trim response bodies larger than 50 KB
_MAX_ARRAY_ITEMS = 50


def _trim_large_arrays(
    obj: object, max_items: int = _MAX_ARRAY_ITEMS, *, _root: bool = True
) -> object:
    """Recursively truncate nested JSON arrays longer than *max_items*.

    The root-level array is never trimmed — it may be a search list or
    record-type list whose entries are all needed.  Only arrays nested
    inside objects (gene records, vocabularies, etc.) are capped.
    """
    if isinstance(obj, list):
        items = obj if _root else obj[:max_items]
        return [_trim_large_arrays(item, max_items, _root=False) for item in items]
    if isinstance(obj, dict):
        return {
            k: _trim_large_arrays(v, max_items, _root=False)
            for k, v in obj.items()
        }
    return obj


def _scrub_request(request):
    """Scrub auth cookies and login credentials from requests before recording.

    User IDs in URLs are hashed to deterministic fakes.
    """
    if "cookie" in request.headers:
        cookie = request.headers["cookie"]
        cookie = re.sub(r"Authorization=[^;]+", "Authorization=SCRUBBED", cookie)
        cookie = re.sub(r"JSESSIONID=[^;]+", "JSESSIONID=SCRUBBED", cookie)
        cookie = re.sub(r"wdk_check_auth=[^;]+", "wdk_check_auth=SCRUBBED", cookie)
        request.headers["cookie"] = cookie

    # Hash user IDs in URL and body
    request.uri = _replace_user_ids(request.uri)

    # CRITICAL: preserve bytes/str type — same fix as _scrub_response.
    if request.body:
        raw = request.body
        was_bytes = isinstance(raw, bytes)
        body = raw.decode("utf-8", errors="replace") if was_bytes else raw
        if isinstance(body, str):
            body = _replace_user_ids(body)
            body = re.sub(r'"password"\s*:\s*"[^"]*"', '"password":"SCRUBBED"', body)
            body = re.sub(
                r'"email"\s*:\s*"[^"]*"', '"email":"test@test.local"', body
            )
            body = _JWT_RE.sub("JWT_SCRUBBED", body)
            request.body = body.encode("utf-8") if was_bytes else body

    return request


def _scrub_response(response):
    """Scrub PII and hash user IDs in response bodies/headers.

    All operations are idempotent — safe during both recording and replay.
    User ID hashing uses a ``999`` prefix; already-hashed IDs are skipped.

    CRITICAL: ``body["string"]`` must stay as ``bytes`` if it was ``bytes``.
    VCR passes it to ``httpcore.Response(content=...)``.  If we convert to
    ``str``, httpcore sets ``stream = str`` which is not ``AsyncIterable``
    and httpx 0.28+ raises ``AssertionError`` during replay.
    """
    headers = response.get("headers", {})

    # Scrub auth cookie values in Set-Cookie headers
    set_cookie = headers.get("Set-Cookie")
    if set_cookie is not None:
        headers["Set-Cookie"] = [
            _COOKIE_SCRUB_RE.sub(r"\1=SCRUBBED", c) for c in set_cookie
        ]

    # Hash user IDs in response headers (Location etc.) — idempotent
    for name in list(headers):
        if name == "Set-Cookie":
            continue
        headers[name] = [_replace_user_ids(v) for v in headers[name]]

    # Scrub PII from response body
    body = response.get("body", {})
    raw = body.get("string", "")
    was_bytes = isinstance(raw, bytes)
    text = raw.decode("utf-8", errors="replace") if was_bytes else raw

    if text and isinstance(text, str):
        # Hash user IDs in response body — idempotent (999-prefixed IDs skipped)
        text = _replace_user_ids(text)
        # PII scrubbing is idempotent
        for pattern, replacement in _PII_PATTERNS:
            text = re.sub(pattern, replacement, text)
        text = _JWT_RE.sub("JWT_SCRUBBED", text)
        text = _EMAIL_RE.sub(
            lambda m: m.group(0) if m.group(0) in _SAFE_EMAILS else "scrubbed@test.local",
            text,
        )

        # Array trimming is done post-hoc via scripts/trim_cassettes.py
        # to avoid breaking tests that depend on exact record counts
        # (e.g., pagination-based gene ID fetching).

        body["string"] = text.encode("utf-8") if was_bytes else text

    return response


def _hashed_path_matcher(r1, r2):
    """Compare URL paths after hashing ``/users/{id}`` to deterministic fakes.

    VCR custom matchers must raise ``AssertionError`` on mismatch.
    """
    from urllib.parse import urlparse  # noqa: PLC0415

    p1 = _replace_user_ids(urlparse(r1.uri).path)
    p2 = _replace_user_ids(urlparse(r2.uri).path)
    assert p1 == p2, f"Path mismatch: {p1} != {p2}"


def _hashed_body_matcher(r1, r2):
    """Compare request bodies after hashing user IDs.

    JSON bodies are parsed and compared structurally to ignore
    whitespace differences (httpx encodes with spaces, VCR/YAML
    may strip them during serialization).

    VCR custom matchers must raise ``AssertionError`` on mismatch.
    """
    b1 = (r1.body or b"")
    b2 = (r2.body or b"")
    if isinstance(b1, bytes):
        b1 = b1.decode("utf-8", errors="replace")
    if isinstance(b2, bytes):
        b2 = b2.decode("utf-8", errors="replace")
    s1 = _replace_user_ids(b1)
    s2 = _replace_user_ids(b2)
    # Try JSON-structural comparison (ignores whitespace)
    try:
        assert json.loads(s1) == json.loads(s2)
    except (json.JSONDecodeError, ValueError):
        assert s1 == s2


def pytest_recording_configure(config, vcr):
    """Register custom matchers that hash user IDs before comparing."""
    vcr.register_matcher("hashed_path", _hashed_path_matcher)
    vcr.register_matcher("hashed_body", _hashed_body_matcher)


@pytest.fixture(scope="session")
def vcr_config():
    """Global VCR configuration for pytest-recording.

    Uses custom matchers that hash user IDs before comparing, so live
    requests (with real IDs) match cassette entries (with hashed IDs).
    """
    return {
        "cassette_library_dir": "src/veupath_chatbot/tests/cassettes",
        "match_on": ["method", "hashed_path", "query", "hashed_body"],
        "before_record_request": _scrub_request,
        "before_record_response": _scrub_response,
        "decode_compressed_response": True,
        "ignore_hosts": ["test"],
    }


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
    monkeypatch.setattr("veupath_chatbot.platform.tasks.spawn", _tracked_spawn)
    monkeypatch.setattr("veupath_chatbot.platform.store.spawn", _tracked_spawn)
    monkeypatch.setattr(
        "veupath_chatbot.services.experiment.core.streaming.spawn",
        _tracked_spawn,
    )

    yield

    # Await all spawned tasks before test teardown
    if pending:
        _done, timed_out = await asyncio.wait(pending, timeout=10.0)
        for t in timed_out:
            t.cancel()
        if timed_out:
            await asyncio.gather(*timed_out, return_exceptions=True)


# ---------------------------------------------------------------------------
# Real WDK fixtures (cassette-backed)
# ---------------------------------------------------------------------------

# Sites eligible for test recording (excluding orthomcl + veupathdb portal)
_TEST_SITES: dict[str, str] = {
    "plasmodb": "https://plasmodb.org/plasmo/service",
    "toxodb": "https://toxodb.org/toxo/service",
    "cryptodb": "https://cryptodb.org/cryptodb/service",
    "giardiadb": "https://giardiadb.org/giardiadb/service",
    "amoebadb": "https://amoebadb.org/amoeba/service",
    "microsporidiadb": "https://microsporidiadb.org/micro/service",
    "piroplasmadb": "https://piroplasmadb.org/piro/service",
    "tritrypdb": "https://tritrypdb.org/tritrypdb/service",
    "trichdb": "https://trichdb.org/trichdb/service",
    "fungidb": "https://fungidb.org/fungidb/service",
    "vectorbase": "https://vectorbase.org/vectorbase/service",
    "hostdb": "https://hostdb.org/hostdb/service",
}


@pytest.fixture
def wdk_test_site(request: pytest.FixtureRequest) -> tuple[str, str]:
    """Pick a deterministic-per-week VEuPathDB site for each test.

    Hashes ``(test node ID, ISO week)`` so the mapping is stable within
    a week (record on Monday, replay all week) but rotates every week.
    Weekly cassette re-recording via CI exercises different sites over time.

    Returns ``(site_id, base_url)`` tuple.
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    # Allow override for testing rotation across weeks.
    override = os.environ.get("VCR_WEEK_OVERRIDE", "").strip()
    iso_week = override or str(datetime.now(tz=UTC).date().isocalendar()[:2])
    key = f"{request.node.nodeid}:{iso_week}"
    sites = list(_TEST_SITES.keys())
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16)  # noqa: S324
    site_id = sites[seed % len(sites)]
    return site_id, _TEST_SITES[site_id]


@pytest.fixture
def wdk_site_id(wdk_test_site: tuple[str, str]) -> str:
    """The site ID portion of wdk_test_site, for passing to create_taxon_step."""
    return wdk_test_site[0]


@pytest.fixture(scope="session")
async def wdk_auth_token() -> str | None:
    """Authenticate to WDK once and return the cross-site auth token.

    The VEuPathDB auth token is valid across ALL sites (plasmodb, toxodb,
    etc.), so we login once via plasmodb and reuse the token everywhere.

    Only meaningful during cassette recording (when ``WDK_AUTH_EMAIL`` is
    set).  During replay, returns ``None`` — cassettes respond regardless.
    """
    email = os.environ.get("WDK_AUTH_EMAIL", "").strip()
    password = os.environ.get("WDK_AUTH_PASSWORD", "").strip()
    if not email or not password:
        return None

    # Login via plasmodb — token works on all VEuPathDB sites.
    async with httpx.AsyncClient(
        base_url="https://plasmodb.org/plasmo/service",
        follow_redirects=False,
        timeout=30.0,
    ) as client:
        response = await client.post(
            "/login",
            json={
                "email": email,
                "password": password,
                "redirectUrl": "https://plasmodb.org",
            },
        )

    # WDK returns TWO Authorization cookies: first is authenticated,
    # second is a new guest session.  We want the first (authenticated).
    for header_name, header_value in response.headers.multi_items():
        if (
            header_name.lower() == "set-cookie"
            and header_value.startswith("Authorization=")
        ):
            return header_value.split(";", 1)[0].split("=", 1)[1].strip('"')

    return None


@pytest.fixture
async def wdk_api(
    wdk_auth_token: str | None,
    wdk_test_site: tuple[str, str],
) -> AsyncGenerator[StrategyAPI]:
    """Real StrategyAPI targeting a per-test random VEuPathDB site.

    Backed by a real ``VEuPathDBClient`` — HTTP calls flow through to WDK
    and are intercepted by VCR cassettes.  The auth token is session-scoped
    (one login), but each test gets a fresh client pointing at its own
    random site.
    """
    _site_id, base_url = wdk_test_site
    client = VEuPathDBClient(
        base_url=base_url,
        timeout=30.0,
        auth_token=wdk_auth_token,
    )
    api = StrategyAPI(client)
    yield api
    await client.close()


@pytest.fixture
async def temp_results_api(
    wdk_api: StrategyAPI,
) -> TemporaryResultsAPI:
    """Properly initialized TemporaryResultsAPI sharing the wdk_api's client.

    Avoids the anti-pattern of setting private attributes
    (``_resolved_user_id``, ``_session_initialized``) directly.
    The ``_ensure_session()`` call is captured by VCR cassettes.
    """
    api = TemporaryResultsAPI(wdk_api.client)
    await api._ensure_session()
    return api


# ---------------------------------------------------------------------------
# Shared test helpers — used by VCR integration tests
# ---------------------------------------------------------------------------

async def create_taxon_step(api: StrategyAPI) -> WDKIdentifier:
    """Create a GenesByTaxon step by dynamically discovering the organism.

    Queries the WDK to find the first available leaf organism for the
    site the ``api`` is targeting.  Works with any VEuPathDB site —
    no static organism mapping needed.
    """
    from veupath_chatbot.domain.parameters.vocab_utils import (  # noqa: PLC0415
        collect_leaf_terms,
    )

    search_response = await api.client.get_search_details(
        "transcript", "GenesByTaxon", expand_params=True,
    )
    organism_value: str | None = None
    for param in search_response.search_data.parameters or []:
        if param.name == "organism" and param.vocabulary is not None:
            if isinstance(param.vocabulary, dict):
                leaves = collect_leaf_terms(param.vocabulary)
                if leaves:
                    organism_value = json.dumps([leaves[0]])
            break

    if organism_value is None:
        msg = "Could not discover organism from GenesByTaxon search parameters"
        raise RuntimeError(msg)

    spec = NewStepSpec(
        search_name="GenesByTaxon",
        search_config=WDKSearchConfig(
            parameters={"organism": organism_value},
        ),
    )
    return await api.create_step(spec, record_type="transcript")


async def materialize_step(api: StrategyAPI, step_id: int) -> int:
    """Create a throw-away strategy so WDK materializes step results.

    Returns the strategy ID (useful for cleanup, but most tests
    ignore it).
    """
    tree = WDKStepTree(step_id=step_id)
    result = await api.create_strategy(
        step_tree=tree, name="vcr-test", is_saved=False
    )
    return result.id


async def discover_organism(api: StrategyAPI) -> str:
    """Discover the first available leaf organism for GenesByTaxon.

    Returns a JSON-encoded list with one organism term, e.g.
    ``'["Plasmodium falciparum 3D7"]'`` on plasmodb.  Works on any
    VEuPathDB site — no static organism mapping needed.
    """
    from veupath_chatbot.domain.parameters.vocab_utils import (  # noqa: PLC0415
        collect_leaf_terms,
    )

    search_response = await api.client.get_search_details(
        "transcript", "GenesByTaxon", expand_params=True,
    )
    for param in search_response.search_data.parameters or []:
        if param.name == "organism" and param.vocabulary is not None:
            if isinstance(param.vocabulary, dict):
                leaves = collect_leaf_terms(param.vocabulary)
                if leaves:
                    return json.dumps([leaves[0]])
            elif isinstance(param.vocabulary, list):
                for item in param.vocabulary:
                    if isinstance(item, list) and item:
                        return json.dumps([str(item[0])])
                    if isinstance(item, str):
                        return json.dumps([item])
    msg = "Could not discover organism from GenesByTaxon search parameters"
    raise RuntimeError(msg)


async def discover_organism_vocab(api: StrategyAPI) -> dict:
    """Get the organism parameter vocabulary tree from GenesByTaxon.

    Returns the raw vocabulary dict (tree structure) for use in
    tests that exercise vocabulary flattening, matching, and
    canonicalization.
    """
    search_response = await api.client.get_search_details(
        "transcript", "GenesByTaxon", expand_params=True,
    )
    for param in search_response.search_data.parameters or []:
        if param.name == "organism" and param.vocabulary is not None and isinstance(param.vocabulary, dict):
            return param.vocabulary
    msg = "No organism vocabulary found in GenesByTaxon"
    raise RuntimeError(msg)


async def discover_leaf_organism(api: StrategyAPI) -> str:
    """Discover the first leaf organism name (not JSON-encoded).

    Useful for text search tests that need a plain organism name.
    """
    from veupath_chatbot.domain.parameters.vocab_utils import (  # noqa: PLC0415
        collect_leaf_terms,
    )

    vocab = await discover_organism_vocab(api)
    leaves = collect_leaf_terms(vocab)
    if not leaves:
        msg = "No leaf organisms found"
        raise RuntimeError(msg)
    return leaves[0]


async def discover_parent_organism(api: StrategyAPI) -> str:
    """Discover an organism parent node that has children.

    Returns the parent term (e.g. "Plasmodium falciparum" on plasmodb).
    Useful for tree vocab tests that need a parent to expand to leaves.
    """
    from veupath_chatbot.domain.parameters.vocab_utils import (  # noqa: PLC0415
        get_node_value,
        get_vocab_children,
    )

    vocab = await discover_organism_vocab(api)

    def _find_parent(node: dict) -> str | None:
        children = get_vocab_children(node)
        if not children:
            return None
        # Check if any child has children (making this a grandparent)
        for child in children:
            if get_vocab_children(child):
                return get_node_value(child) or None
        # Otherwise this node itself is a parent of leaves
        return get_node_value(node) or None

    result = _find_parent(vocab)
    if result is None:
        msg = "No parent organism node found in vocabulary"
        raise RuntimeError(msg)
    return result


async def discover_gene_ids(api: StrategyAPI, limit: int = 5) -> list[str]:
    """Create a step, materialize it, and return gene IDs from results.

    Useful for gene lookup tests that need real gene IDs from
    whichever VEuPathDB site the test is targeting.
    """
    from veupath_chatbot.services.wdk.step_results import (  # noqa: PLC0415
        StepResultsService,
    )

    step = await create_taxon_step(api)
    await materialize_step(api, step.id)
    svc = StepResultsService(api, step_id=step.id, record_type="transcript")
    result = await svc.get_records(offset=0, limit=limit)
    gene_ids: list[str] = []
    for record in result.records:
        for part in record.id:
            if isinstance(part, dict) and part.get("name") in (
                "source_id",
                "gene_source_id",
            ):
                gene_ids.append(str(part["value"]))
                break
    return gene_ids
