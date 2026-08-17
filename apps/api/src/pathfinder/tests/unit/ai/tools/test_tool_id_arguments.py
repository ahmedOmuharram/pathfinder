"""An id the model got wrong is a retry, not a dead turn.

Both tools take a PathFinder UUID while the conversation is full of WDK
numeric ids. Parsing one with `UUID()` raises ValueError, which no phase
catches, so the whole turn ends with a Python message the user cannot act on.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.tools.standalone.control_sets import (
    import_control_ids_from_strategy,
)
from pathfinder.ai.tools.standalone.scored_comparison import compare_variants_scored
from pathfinder.services.experiment.variant_comparison import VariantSpec

_WDK_STRATEGY_ID = "330531493"


class _SessionCM:
    async def __aenter__(self) -> Any:
        return MagicMock()

    async def __aexit__(self, *args: Any) -> bool:
        return False


def _ctx() -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.runtime.site_id = "plasmodb"
    ctx.deps.runtime.user_id = uuid4()
    ctx.deps.runtime.db_session_factory = MagicMock(return_value=_SessionCM())
    return ctx


def _variants() -> list[VariantSpec]:
    return [
        VariantSpec(label="a", search_name="GenesByText", parameters={}),
        VariantSpec(label="b", search_name="GenesByMolecularWeight", parameters={}),
    ]


class TestAWdkStrategyIdIsARetry:
    @pytest.mark.asyncio
    async def test_it_does_not_raise_value_error(self) -> None:
        with pytest.raises(ModelRetry):
            await import_control_ids_from_strategy(_ctx(), _WDK_STRATEGY_ID)

    @pytest.mark.asyncio
    async def test_the_message_names_the_value_it_got(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await import_control_ids_from_strategy(_ctx(), _WDK_STRATEGY_ID)

        assert _WDK_STRATEGY_ID in str(err.value)

    @pytest.mark.asyncio
    async def test_the_message_says_which_id_is_wanted(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await import_control_ids_from_strategy(_ctx(), _WDK_STRATEGY_ID)

        assert "conversation" in str(err.value).lower()


class TestAControlSetIdIsARetry:
    @pytest.mark.asyncio
    async def test_a_non_uuid_control_set_is_a_retry(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await compare_variants_scored(_ctx(), _variants(), _WDK_STRATEGY_ID)

        assert "control" in str(err.value).lower()

    @pytest.mark.asyncio
    async def test_a_name_instead_of_an_id_is_a_retry(self) -> None:
        with pytest.raises(ModelRetry):
            await compare_variants_scored(_ctx(), _variants(), "my controls")
