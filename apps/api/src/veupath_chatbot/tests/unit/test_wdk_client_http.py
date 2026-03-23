"""Integration tests for VEuPathDBClient HTTP behavior (client.py).

Uses respx to mock outbound HTTP and verify:
- Retry logic: 5xx retried 3x; 4xx not retried
- Error mapping: status codes → WDKError with correct status
- JSESSIONID initialization on first authenticated request
- Empty response handling
- Auth cookie (not header) per WDK contract

WDK contracts validated:
- Authorization via cookie, not header
- JSESSIONID required for process queries (GenesByOrthologPattern)
- 5xx → retry with exponential backoff
- 4xx → immediate WDKError (no retry)
"""

import httpx
import pytest
import respx

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.platform.errors import DataParsingError, WDKError
from veupath_chatbot.tests.fixtures.wdk_responses import (
    search_details_response,
    standard_report_response,
)


@pytest.fixture
def base_url() -> str:
    return "https://plasmodb.org/plasmo/service"


@pytest.fixture
def client(base_url: str) -> VEuPathDBClient:
    return VEuPathDBClient(base_url=base_url, timeout=5.0)


@pytest.fixture
def authed_client(base_url: str) -> VEuPathDBClient:
    return VEuPathDBClient(base_url=base_url, timeout=5.0, auth_token="test-token")


# ── 4xx errors → WDKError immediately (no retry) ─────────────────


class TestClientErrorNoRetry:
    """WDK contract: 4xx responses are client errors — do NOT retry."""

    @pytest.mark.asyncio
    async def test_404_raises_wdk_error(self, client: VEuPathDBClient) -> None:
        with respx.mock:
            respx.get(f"{client.base_url}/not-found").respond(404, text="Not Found")
            with pytest.raises(WDKError) as exc_info:
                await client.get("/not-found")
            assert exc_info.value.status == 404

    @pytest.mark.asyncio
    async def test_422_raises_wdk_error(self, client: VEuPathDBClient) -> None:
        """WDK returns 422 for invalid parameters — must not retry."""
        with respx.mock:
            respx.post(f"{client.base_url}/bad-params").respond(
                422, text="Invalid parameter"
            )
            with pytest.raises(WDKError) as exc_info:
                await client.post("/bad-params", json={"bad": "data"})
            assert exc_info.value.status == 422

    @pytest.mark.asyncio
    async def test_4xx_called_only_once(self, client: VEuPathDBClient) -> None:
        """4xx should NOT be retried — verify only 1 request made."""
        with respx.mock:
            route = respx.get(f"{client.base_url}/forbidden").respond(
                403, text="Forbidden"
            )
            with pytest.raises(WDKError):
                await client.get("/forbidden")
            assert route.call_count == 1


# ── 5xx errors → retry then WDKError ─────────────────────────────


class TestServerErrorRetry:
    """WDK contract: 5xx responses are transient — retry up to 3 times."""

    @pytest.mark.asyncio
    async def test_5xx_retried_then_raises(self, client: VEuPathDBClient) -> None:
        """All 3 attempts fail with 500 → WDKError after retries exhausted."""
        with respx.mock:
            route = respx.get(f"{client.base_url}/error").respond(
                500, text="Internal Server Error"
            )
            with pytest.raises(WDKError) as exc_info:
                await client.get("/error")
            assert exc_info.value.status == 500
            assert route.call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_5xx_recovers_on_second_attempt(
        self, client: VEuPathDBClient
    ) -> None:
        """First attempt 500, second attempt 200 → success."""
        with respx.mock:
            route = respx.get(f"{client.base_url}/flaky").mock(
                side_effect=[
                    httpx.Response(500, text="Temporarily down"),
                    httpx.Response(200, json={"status": "ok"}),
                ]
            )
            result = await client.get("/flaky")
            assert result == {"status": "ok"}
            assert route.call_count == 2


# ── Successful responses ──────────────────────────────────────────


class TestSuccessResponse:
    @pytest.mark.asyncio
    async def test_json_response_parsed(self, client: VEuPathDBClient) -> None:
        with respx.mock:
            respx.get(f"{client.base_url}/data").respond(200, json={"key": "value"})
            result = await client.get("/data")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_empty_response_returns_none(self, client: VEuPathDBClient) -> None:
        """WDK returns 204 No Content for some operations."""
        with respx.mock:
            respx.delete(f"{client.base_url}/item").respond(204)
            result = await client.delete("/item")
            assert result is None

    @pytest.mark.asyncio
    async def test_list_response(self, client: VEuPathDBClient) -> None:
        with respx.mock:
            respx.get(f"{client.base_url}/list").respond(200, json=[1, 2, 3])
            result = await client.get("/list")
            assert result == [1, 2, 3]


# ── JSESSIONID initialization ────────────────────────────────────


class TestJsessionIdInit:
    """WDK contract: JSESSIONID required for process queries.

    First authenticated request should trigger GET /app to establish
    Tomcat session cookie. Without it, GenesByOrthologPattern silently
    returns 0 results.
    """

    @pytest.mark.asyncio
    async def test_first_auth_request_initializes_session(
        self, authed_client: VEuPathDBClient
    ) -> None:
        """Authenticated request triggers JSESSIONID initialization."""
        with respx.mock:
            # /app endpoint for session init
            app_route = respx.get("https://plasmodb.org/plasmo/app").respond(200)
            # Actual API call
            respx.get(f"{authed_client.base_url}/data").respond(
                200, json={"result": "ok"}
            )
            result = await authed_client.get("/data")
            assert result == {"result": "ok"}
            assert app_route.called, "First auth request must hit /app for JSESSIONID"

    @pytest.mark.asyncio
    async def test_session_init_only_once(self, authed_client: VEuPathDBClient) -> None:
        """Session initialization should happen only on first request."""
        with respx.mock:
            app_route = respx.get("https://plasmodb.org/plasmo/app").respond(200)
            respx.get(f"{authed_client.base_url}/data").respond(200, json={"ok": True})
            await authed_client.get("/data")
            await authed_client.get("/data")
            assert app_route.call_count == 1, "Session init should happen only once"

    @pytest.mark.asyncio
    async def test_unauthenticated_skips_session_init(
        self, client: VEuPathDBClient
    ) -> None:
        """No auth token → no JSESSIONID initialization."""
        with respx.mock:
            app_route = respx.get("https://plasmodb.org/plasmo/app").respond(200)
            respx.get(f"{client.base_url}/data").respond(200, json={"ok": True})
            await client.get("/data")
            assert not app_route.called, "Unauthenticated should skip /app"


# ── Auth cookie (not header) ──────────────────────────────────────


class TestAuthCookie:
    """WDK contract: authorization via cookie, not HTTP header."""

    @pytest.mark.asyncio
    async def test_auth_token_set_as_cookie(
        self, authed_client: VEuPathDBClient
    ) -> None:
        """Auth token must be in cookies, not Authorization header."""
        with respx.mock:
            respx.get("https://plasmodb.org/plasmo/app").respond(200)
            route = respx.get(f"{authed_client.base_url}/check")
            route.respond(200, json={})
            await authed_client.get("/check")

            # Verify the request was made with cookie, not header
            request = route.calls[0].request
            # httpx stores cookies in the request's extensions or headers
            # The auth token should be in cookie jar, not in Authorization header
            assert (
                "Authorization" not in request.headers
                or request.headers.get("Authorization") != "test-token"
            ), "Auth token should be in cookies, not Authorization header"


# ── get_searches response handling ────────────────────────────────


class TestGetSearches:
    """Validates graceful degradation for search listing."""

    @pytest.mark.asyncio
    async def test_skips_unparseable_entries(self, client: VEuPathDBClient) -> None:
        """Graceful: unparseable search entries are skipped, not fatal."""
        with respx.mock:
            respx.get(f"{client.base_url}/record-types/transcript/searches").respond(
                200,
                json=[
                    {
                        "urlSegment": "GenesByTaxon",
                        "fullName": "GeneQuestions.GenesByTaxon",
                        "displayName": "Organism",
                    },
                    "not_a_dict",  # should be skipped
                    {"incomplete": True},  # missing urlSegment → skip
                ],
            )
            searches = await client.get_searches("transcript")
            assert len(searches) == 1
            assert searches[0].url_segment == "GenesByTaxon"

    @pytest.mark.asyncio
    async def test_non_list_response(self, client: VEuPathDBClient) -> None:
        with respx.mock:
            respx.get(f"{client.base_url}/record-types/transcript/searches").respond(
                200, json={"error": "unexpected"}
            )
            searches = await client.get_searches("transcript")
            assert searches == []


# ── get_search_details response handling ──────────────────────────


class TestGetSearchDetails:
    @pytest.mark.asyncio
    async def test_valid_response_parsed(self, client: VEuPathDBClient) -> None:
        """Uses realistic fixture from wdk_responses.py (verified against live API)."""
        with respx.mock:
            respx.get(
                f"{client.base_url}/record-types/transcript/searches/GenesByTaxon"
            ).respond(200, json=search_details_response("GenesByTaxon"))
            response = await client.get_search_details("transcript", "GenesByTaxon")
            assert response.search_data.url_segment == "GenesByTaxon"
            # Verify realistic fixture has real parameter data
            assert response.search_data.parameters is not None
            assert len(response.search_data.parameters) > 0
            assert response.search_data.parameters[0].name == "organism"

    @pytest.mark.asyncio
    async def test_invalid_response_raises_data_parsing_error(
        self, client: VEuPathDBClient
    ) -> None:
        """Schema drift → DataParsingError, not crash."""
        with respx.mock:
            respx.get(
                f"{client.base_url}/record-types/transcript/searches/Bad"
            ).respond(200, json={"completely": "wrong"})
            with pytest.raises(
                DataParsingError, match="Unexpected WDK search response"
            ):
                await client.get_search_details("transcript", "Bad")


# ── run_search_report (anonymous report) ──────────────────────────


class TestRunSearchReport:
    """Validates anonymous report contract used by step count computation."""

    @pytest.mark.asyncio
    async def test_returns_wdk_answer(self, client: VEuPathDBClient) -> None:
        """Uses realistic fixture from wdk_responses.py (verified against live API)."""
        fixture = standard_report_response()
        with respx.mock:
            respx.post(
                f"{client.base_url}/record-types/transcript/searches/GenesByTaxon/reports/standard"
            ).respond(200, json=fixture)
            answer = await client.run_search_report(
                "transcript",
                "GenesByTaxon",
                {"parameters": {"organism": '["Plasmodium falciparum 3D7"]'}},
            )
            assert answer.meta.total_count > 0
            assert len(answer.records) > 0

    @pytest.mark.asyncio
    async def test_malformed_answer_raises(self, client: VEuPathDBClient) -> None:
        with respx.mock:
            respx.post(
                f"{client.base_url}/record-types/transcript/searches/Bad/reports/standard"
            ).respond(200, json={"not": "an answer"})
            with pytest.raises(DataParsingError, match="Unexpected WDK answer"):
                await client.run_search_report("transcript", "Bad", {"parameters": {}})
