"""Contextualizing a search's parameters is an enrichment, not a precondition.

Six call sites asked WDK for "this search's parameters under this context" and
each invented its own failure policy: two had none at all, the rest caught four
different exception types and recovered four different ways. The two with none
are where the bugs landed.

Proven on live PlasmoDB, ``GenesByOrthologPattern``:

    refresh, organism = ["Plasmodium falciparum 3D7"] + profile_pattern -> 500
    RUN,     same values, gold parameter set                            -> 200, totalCount 3347

WDK returns 500 on the endpoint that narrows a child's vocabulary, for a value
it accepts and executes on the endpoint that runs the search. Nothing we send is
invalid. Abandoning the criterion there cost the entire 16-step strategy.

The contextualized view narrows vocabularies. Losing it costs vocabulary
precision; it must never cost the search.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.integrations.veupathdb.search_context import (
    get_search_params_under_context,
)
from pathfinder.platform.errors import AppError, WDKError


def _response(marker: str) -> Any:
    response = MagicMock()
    response.search_data.parameters = [marker]
    return response


def _client(*, contextual: Any, plain: Any) -> Any:
    client = MagicMock()
    client.get_search_details_with_params = (
        AsyncMock(side_effect=contextual)
        if isinstance(contextual, BaseException)
        else AsyncMock(return_value=contextual)
    )
    client.get_search_details = (
        AsyncMock(side_effect=plain)
        if isinstance(plain, BaseException)
        else AsyncMock(return_value=plain)
    )
    return client


class TestContextIsUsedWhenItWorks:
    @pytest.mark.asyncio
    async def test_returns_the_contextualized_view(self) -> None:
        client = _client(contextual=_response("narrowed"), plain=_response("static"))

        result = await get_search_params_under_context(
            client, "transcript", "GenesByOrthologPattern", {"organism": "[]"}
        )

        assert result.search_data.parameters == ["narrowed"]

    @pytest.mark.asyncio
    async def test_passes_the_context_through(self) -> None:
        client = _client(contextual=_response("narrowed"), plain=_response("static"))

        await get_search_params_under_context(
            client, "transcript", "S", {"profile_pattern": "%pfal:Y%"}
        )

        kwargs = client.get_search_details_with_params.await_args.kwargs
        assert kwargs["context"] == {"profile_pattern": "%pfal:Y%"}

    @pytest.mark.asyncio
    async def test_an_empty_context_skips_the_contextual_call(self) -> None:
        # Nothing to narrow by; the POST would only cost a round trip.
        client = _client(contextual=_response("narrowed"), plain=_response("static"))

        result = await get_search_params_under_context(client, "transcript", "S", {})

        assert result.search_data.parameters == ["static"]
        client.get_search_details_with_params.assert_not_awaited()


class TestContextFailureDegrades:
    @pytest.mark.asyncio
    async def test_a_5xx_falls_back_to_the_static_view(self) -> None:
        client = _client(
            contextual=WDKError("500 Internal Error", status=500),
            plain=_response("static"),
        )

        result = await get_search_params_under_context(
            client, "transcript", "GenesByOrthologPattern", {"organism": "[]"}
        )

        assert result.search_data.parameters == ["static"]

    @pytest.mark.asyncio
    async def test_does_not_raise_when_wdk_cannot_contextualize(self) -> None:
        client = _client(
            contextual=WDKError("boom", status=500), plain=_response("static")
        )

        await get_search_params_under_context(client, "transcript", "S", {"a": "b"})

    @pytest.mark.asyncio
    async def test_still_raises_when_the_search_itself_is_unreachable(self) -> None:
        # Both endpoints down is a real outage, not a narrowing we can skip.
        client = _client(
            contextual=WDKError("boom", status=500),
            plain=WDKError("also boom", status=500),
        )

        with pytest.raises(AppError):
            await get_search_params_under_context(client, "transcript", "S", {"a": "b"})
