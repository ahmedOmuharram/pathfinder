"""``fetch_search_details`` raises a ``Search not found`` validation error
whose detail carries did-you-mean suggestions, so the model-facing error
directive (which uses ``str(error)``) can guide self-correction instead of
looping on invented names."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.domain.search import SearchContext
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.errors import ValidationError as CoreValidationError
from pathfinder.services.catalog import param_discovery


def _search(name: str) -> Any:
    s = MagicMock()
    s.url_segment = name
    return s


@pytest.mark.asyncio
async def test_search_not_found_detail_includes_did_you_mean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery = MagicMock()
    discovery.get_search_details = AsyncMock(
        side_effect=AppError(
            code=ErrorCode.WDK_ERROR, title="x", status=404, detail="404"
        )
    )
    discovery.get_searches = AsyncMock(
        return_value=[_search("GenesByText"), _search("GenesByGoTerm")]
    )
    monkeypatch.setattr(param_discovery, "get_discovery_service", lambda: discovery)

    ctx = SearchContext(
        site_id="vectorbase",
        record_type="transcript",
        search_name="GeneByTextSearch",
    )

    with pytest.raises(CoreValidationError) as excinfo:
        await param_discovery.fetch_search_details(ctx, record_types=[])

    err = excinfo.value
    assert "GenesByText" in err.detail
    assert "GeneByTextSearch" in err.detail
