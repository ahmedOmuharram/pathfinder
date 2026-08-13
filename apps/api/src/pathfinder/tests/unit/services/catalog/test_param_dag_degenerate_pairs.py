"""Tests for same-vocabulary sibling resolution and the degenerate-pair rule.

A WDK expression search pairs a reference and a comparison selector drawn from
one vocabulary. Both selectors on the same value compare a group to itself and
return zero rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from pathfinder.domain.parameters.values import (
    MultiPickValue,
    ParamValue,
    SinglePickValue,
)
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.integrations.embeddings.prefixes import SEARCH_QUERY_PREFIX
from pathfinder.services.catalog.param_dag import (
    ParameterInfo,
    ParamFetcher,
    resolve_params_with_intent,
)
from pathfinder.services.catalog.param_intent import ParamIntent

MALE = VocabOption(value="male", display="male")
FEMALE = VocabOption(value="female", display="female")
SEXES = [MALE, FEMALE]
AVERAGE_ONLY = [VocabOption(value="average1", display="average")]


def _p(
    name: str,
    param_type: str,
    *,
    allowed: list[VocabOption] | None = None,
    default: str | None = None,
    required: bool = True,
    depends_on: list[str] | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type=param_type,
        required=required,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        allowed_values=allowed,
        vocab_depends_on=depends_on,
    )


async def _embed_prefers_female(texts: Sequence[str]) -> list[list[float]]:
    """Make the matcher pick ``female`` for both sex selectors."""
    return [
        [1.0, 0.0] if t.startswith(SEARCH_QUERY_PREFIX) or "female" in t else [0.0, 1.0]
        for t in texts
    ]


async def _embed_orthogonal(texts: Sequence[str]) -> list[list[float]]:
    return [
        [1.0, 0.0] if t.startswith(SEARCH_QUERY_PREFIX) else [0.0, 1.0] for t in texts
    ]


def _values(param: ParamValue) -> list[str]:
    """Normalize either param kind to a list of bare vocabulary terms."""
    if isinstance(param, MultiPickValue):
        return list(param.values)
    if isinstance(param, SinglePickValue):
        return [param.value]
    msg = f"unexpected param value: {param!r}"
    raise AssertionError(msg)


def _assert_no_degenerate_pair(
    params: Mapping[str, ParamValue], a: str, b: str
) -> None:
    if a in params and b in params:
        assert _values(params[a]) != _values(params[b]), (
            f"degenerate pair: {a} and {b} both bound to {_values(params[a])}"
        )


# --- fetcher shapes ------------------------------------------------------------


def _vectorbase_microarray_fetch() -> ParamFetcher:
    """A fold-change search shape with a deferred dependent selector.

    ``samples_fc_comp_generic`` depends on ``profileset``, so it resolves in a
    later pass and its vocabulary is narrower until the parent binds.
    """

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        resolved_parent = "profileset" in context
        return [
            _p(
                "profileset",
                "single-pick-vocabulary",
                allowed=[VocabOption(value="ps1", display="Profile Set 1")],
            ),
            _p("samples_fc_ref_generic", "multi-pick-vocabulary", allowed=SEXES),
            _p(
                "samples_fc_comp_generic",
                "multi-pick-vocabulary",
                allowed=SEXES if resolved_parent else [FEMALE],
                depends_on=["profileset"],
            ),
            _p(
                "min_max_avg_ref",
                "single-pick-vocabulary",
                allowed=AVERAGE_ONLY,
                default="average1",
            ),
            _p(
                "min_max_avg_comp",
                "single-pick-vocabulary",
                allowed=AVERAGE_ONLY,
                default="average1",
                depends_on=["profileset"],
            ),
        ]

    return fetch_at


@pytest.mark.asyncio
async def test_single_option_operation_pair_binds_even_when_deferred() -> None:
    """A param with one legal value binds from its default, even when deferred,
    and never becomes an open slot."""
    rp = await resolve_params_with_intent(
        fetch_at=_vectorbase_microarray_fetch(),
        intent=ParamIntent(organism_scope=None, text="female versus male"),
        embed=_embed_orthogonal,
    )
    assert _values(rp.params["min_max_avg_ref"]) == ["average1"]
    assert _values(rp.params["min_max_avg_comp"]) == ["average1"]
    assert not any(s.param_name.startswith("min_max_avg") for s in rp.open_slots)


@pytest.mark.asyncio
async def test_override_evicts_guess_across_a_deferred_dependency() -> None:
    """An override on a deferred param evicts the sibling guess that already
    holds the same value, and the sibling is deduced again."""
    rp = await resolve_params_with_intent(
        fetch_at=_vectorbase_microarray_fetch(),
        intent=ParamIntent(organism_scope=None, text="upregulated in female adults"),
        embed=_embed_prefers_female,
        overrides={"samples_fc_comp_generic": "female"},
    )
    assert _values(rp.params["samples_fc_comp_generic"]) == ["female"]
    assert _values(rp.params["samples_fc_ref_generic"]) == ["male"]
    _assert_no_degenerate_pair(
        rp.params, "samples_fc_ref_generic", "samples_fc_comp_generic"
    )
    assert rp.open_slots == []


@pytest.mark.asyncio
async def test_both_selectors_pinned_is_honored_verbatim() -> None:
    rp = await resolve_params_with_intent(
        fetch_at=_vectorbase_microarray_fetch(),
        intent=ParamIntent(organism_scope=None, text="upregulated in female adults"),
        embed=_embed_prefers_female,
        overrides={
            "samples_fc_ref_generic": "male",
            "samples_fc_comp_generic": "female",
        },
    )
    assert _values(rp.params["samples_fc_ref_generic"]) == ["male"]
    assert _values(rp.params["samples_fc_comp_generic"]) == ["female"]
    assert rp.open_slots == []


@pytest.mark.asyncio
async def test_unpinned_contrast_resolves_in_the_direction_the_user_asked() -> None:
    """WDK computes fold change as comparison against reference, so the named
    group binds to the comparison selector."""
    rp = await resolve_params_with_intent(
        fetch_at=_vectorbase_microarray_fetch(),
        intent=ParamIntent(organism_scope=None, text="upregulated in female adults"),
        embed=_embed_prefers_female,
    )
    assert _values(rp.params["samples_fc_comp_generic"]) == ["female"]
    assert _values(rp.params["samples_fc_ref_generic"]) == ["male"]
    _assert_no_degenerate_pair(
        rp.params, "samples_fc_ref_generic", "samples_fc_comp_generic"
    )


# --- eviction rules ------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_override_never_evicts_another_override() -> None:
    """Two explicit picks that collide are both honored."""

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p("ref", "multi-pick-vocabulary", allowed=SEXES),
            _p("comp", "multi-pick-vocabulary", allowed=SEXES),
        ]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="anything"),
        embed=_embed_orthogonal,
        overrides={"ref": "female", "comp": "female"},
    )
    assert _values(rp.params["ref"]) == ["female"]
    assert _values(rp.params["comp"]) == ["female"]


@pytest.mark.asyncio
async def test_eviction_asks_when_more_than_one_option_remains() -> None:
    """An evicted param with more than one remaining option becomes an open
    slot instead of a guess."""
    three = [
        VocabOption(value="a", display="a"),
        VocabOption(value="b", display="b"),
        VocabOption(value="c", display="c"),
    ]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p("ref", "single-pick-vocabulary", allowed=three, default="a"),
            _p("comp", "single-pick-vocabulary", allowed=three, default="a"),
        ]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="no match"),
        embed=_embed_orthogonal,
        overrides={"comp": "a"},
    )
    assert _values(rp.params["comp"]) == ["a"]
    _assert_no_degenerate_pair(rp.params, "ref", "comp")
    assert any(s.param_name == "ref" for s in rp.open_slots)


@pytest.mark.asyncio
async def test_override_on_an_unrelated_vocabulary_evicts_nothing() -> None:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p("sex", "single-pick-vocabulary", allowed=SEXES, default="female"),
            _p(
                "direction",
                "single-pick-vocabulary",
                allowed=[
                    VocabOption(value="up", display="Up"),
                    VocabOption(value="down", display="Down"),
                ],
                default="up",
            ),
        ]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="no match"),
        embed=_embed_orthogonal,
        overrides={"direction": "down"},
    )
    assert _values(rp.params["sex"]) == ["female"], "unrelated param must survive"
    assert _values(rp.params["direction"]) == ["down"]
    assert rp.open_slots == []


@pytest.mark.asyncio
async def test_three_same_vocab_siblings_never_collide() -> None:
    """Eviction never leaves two same-vocabulary siblings on one value."""
    three = [
        VocabOption(value="a", display="a"),
        VocabOption(value="b", display="b"),
        VocabOption(value="c", display="c"),
    ]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p("s1", "single-pick-vocabulary", allowed=three, default="a"),
            _p("s2", "single-pick-vocabulary", allowed=three, default="a"),
            _p("s3", "single-pick-vocabulary", allowed=three, default="a"),
        ]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="no match"),
        embed=_embed_orthogonal,
        overrides={"s3": "a"},
    )
    bound = {n: _values(v) for n, v in rp.params.items() if n in {"s1", "s2", "s3"}}
    assert len(set(map(tuple, bound.values()))) == len(bound), (
        f"two siblings share a value: {bound}"
    )


# --- termination ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_swapped_overrides_terminate_and_are_honored() -> None:
    """Overrides that each want the other guessed value settle without a
    repeated eviction loop."""

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            _p("ref", "single-pick-vocabulary", allowed=SEXES, default="male"),
            _p("comp", "single-pick-vocabulary", allowed=SEXES, default="female"),
        ]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="no match"),
        embed=_embed_orthogonal,
        overrides={"ref": "female", "comp": "male"},
    )
    assert _values(rp.params["ref"]) == ["female"]
    assert _values(rp.params["comp"]) == ["male"]


@pytest.mark.asyncio
async def test_every_required_param_is_either_bound_or_asked_about() -> None:
    """Every required param comes back either as a binding or as an open
    slot."""
    rp = await resolve_params_with_intent(
        fetch_at=_vectorbase_microarray_fetch(),
        intent=ParamIntent(organism_scope=None, text="upregulated in female adults"),
        embed=_embed_prefers_female,
        overrides={"samples_fc_comp_generic": "female"},
    )
    accounted = set(rp.params) | {s.param_name for s in rp.open_slots}
    required = {
        "profileset",
        "samples_fc_ref_generic",
        "samples_fc_comp_generic",
        "min_max_avg_ref",
        "min_max_avg_comp",
    }
    assert required <= accounted, f"lost params: {sorted(required - accounted)}"


@pytest.mark.asyncio
async def test_aggregation_selectors_may_share_a_value() -> None:
    """An aggregation operation selects how to collapse replicates on one side,
    not which samples the side contains, so both sides may share a value."""
    ops = [
        VocabOption(value="average1", display="average"),
        VocabOption(value="median2", display="median"),
        VocabOption(value="minimum2", display="minimum"),
        VocabOption(value="maximum2", display="maximum"),
    ]

    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        return [
            ParameterInfo(
                name="min_max_avg_ref",
                display_name="Operation Applied to Reference Samples",
                type="single-pick-vocabulary",
                required=True,
                is_visible=True,
                help="",
                value_format="",
                default_value="average1",
                allowed_values=ops,
            ),
            ParameterInfo(
                name="min_max_avg_comp",
                display_name="Operation Applied to Comparison Samples",
                type="single-pick-vocabulary",
                required=True,
                is_visible=True,
                help="",
                value_format="",
                default_value="average1",
                allowed_values=ops,
            ),
        ]

    rp = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(organism_scope=None, text="female versus male"),
        embed=_embed_orthogonal,
    )
    assert _values(rp.params["min_max_avg_ref"]) == ["average1"]
    assert _values(rp.params["min_max_avg_comp"]) == ["average1"]
    assert rp.open_slots == []
