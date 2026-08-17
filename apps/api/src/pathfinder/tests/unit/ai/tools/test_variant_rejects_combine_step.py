"""A variant names a WDK search. A combine step is not one.

The live strategy renders a combine step as "Combine", so that word reaches
the variant tools as a search name. WDK rejects it once the run reaches the
server, which spends the run and reports no metric.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.tools.standalone._variant_targets import reject_combine_variants
from pathfinder.ai.tools.standalone.scored_comparison import compare_variants_scored
from pathfinder.ai.tools.standalone.variant_comparison import compare_search_variants
from pathfinder.services.experiment.variant_comparison import VariantSpec


class _SessionCM:
    async def __aenter__(self) -> Any:
        return MagicMock()

    async def __aexit__(self, *_a: Any) -> bool:
        return False


def _ctx() -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.runtime.site_id = "plasmodb"
    ctx.deps.runtime.user_id = uuid4()
    ctx.deps.runtime.db_session_factory = MagicMock(return_value=_SessionCM())
    return ctx


def _with(name: str) -> list[VariantSpec]:
    return [
        VariantSpec(label="a", search_name=name, parameters={}),
        VariantSpec(label="b", search_name="GenesByText", parameters={}),
    ]


class TestTheScoredToolRefusesACombineStep:
    @pytest.mark.asyncio
    async def test_the_display_label_is_rejected(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await compare_variants_scored(_ctx(), _with("Combine"), str(uuid4()))

        assert "Combine" in str(err.value)

    @pytest.mark.asyncio
    async def test_the_sentinel_is_rejected(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await compare_variants_scored(_ctx(), _with("__combine__"), str(uuid4()))

        assert "__combine__" in str(err.value)

    @pytest.mark.asyncio
    async def test_the_message_names_the_tool_that_takes_a_step(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await compare_variants_scored(_ctx(), _with("Combine"), str(uuid4()))

        assert "run_control_tests_on_step" in str(err.value)

    @pytest.mark.asyncio
    async def test_the_offending_label_is_named(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await compare_variants_scored(_ctx(), _with("Combine"), str(uuid4()))

        assert "a" in str(err.value)


class TestTheUnscoredToolRefusesItToo:
    @pytest.mark.asyncio
    async def test_a_combine_step_is_rejected(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await compare_search_variants(_ctx(), _with("Combine"))

        assert "run_control_tests_on_step" in str(err.value)


class TestARealSearchStillPasses:
    def test_the_guard_does_not_fire_on_search_names(self) -> None:
        reject_combine_variants(_with("GenesByMolecularWeight"))

    def test_a_search_whose_name_contains_the_word_is_allowed(self) -> None:
        reject_combine_variants(_with("GenesByCombinedScore"))
