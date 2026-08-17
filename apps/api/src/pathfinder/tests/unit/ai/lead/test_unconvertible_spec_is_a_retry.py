"""A structure the converter refuses is a retry, not a dead turn.

``ready_to_build`` reports that every criterion is bound and a structure
exists. It does not run the conversion, so a spec can pass it and still fail
to become a step tree - after FRAME has spent the expensive part of the turn.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.lead.sub_agent_dispatch import build_strategy
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
    SpecStructure,
    StructureNode,
)


def _unconvertible() -> OperationalSpec:
    # Two inputs and no operator: bound, structured, and not a tree.
    return OperationalSpec(
        goal="drug targets",
        criteria=[
            Criterion(id=n, text=n, role="filter", search_name=f"By{n}")
            for n in ("a", "b")
        ],
        structure=SpecStructure(
            root=StructureNode(
                kind="combine",
                inputs=[
                    StructureNode(kind="leaf", criterion_id="a"),
                    StructureNode(kind="leaf", criterion_id="b"),
                ],
            )
        ),
    )


def _ctx(spec: OperationalSpec) -> Any:
    ctx = MagicMock()
    ctx.deps.state.operational_spec = spec
    ctx.deps.runtime.user_id = uuid4()
    return ctx


class TestTheTurnSurvives:
    @pytest.mark.asyncio
    async def test_it_raises_model_retry(self) -> None:
        spec = _unconvertible()
        assert spec.ready_to_build

        with pytest.raises(ModelRetry):
            await build_strategy(_ctx(spec))

    @pytest.mark.asyncio
    async def test_the_message_names_the_problem(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await build_strategy(_ctx(_unconvertible()))

        assert "combine" in str(err.value)

    @pytest.mark.asyncio
    async def test_the_message_says_the_structure_is_at_fault(self) -> None:
        with pytest.raises(ModelRetry) as err:
            await build_strategy(_ctx(_unconvertible()))

        assert "structure" in str(err.value).lower()
