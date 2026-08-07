"""Same-vocabulary sibling resolution: the degenerate-pair invariant.

WDK expression searches pair a *reference* and a *comparison* selector drawn
from one vocabulary. Landing both on the same value compares a group to itself
and returns zero rows -- silently, with a valid-looking strategy. Every test
here pins one rule or one shape that produced a real bug.

The shapes matter more than the assertions. Earlier tests here used a
simplified single-pass, static-vocabulary mock and passed while production was
broken three separate ways:

* ``vocab_depends_on`` defers a param to a LATER resolution pass, so a sibling
  binds before the deferred param is ever considered (ordering cannot fix it).
* A param's vocabulary CHANGES between passes as its parent resolves, so its
  signature is not stable across the walk.
* Multi-pick values serialize to a JSON array on the wire but are matched as
  bare terms, so bookkeeping keyed on the wrong form silently never matches.
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
    """Make the slot-agnostic matcher pick ``female`` for BOTH sex selectors."""
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


# --- the real VectorBase shape -------------------------------------------------


def _vectorbase_microarray_fetch() -> ParamFetcher:
    """The GSE22339 male-vs-female fold-change shape.

    ``samples_fc_comp_generic`` depends on ``profileset``, so it is deferred to
    a later pass, and its vocabulary is narrower until the parent resolves --
    both properties that broke earlier fixes.
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
    """The originally reported hang: ``min_max_avg_comp`` has ONE legal value,
    WDK ships it as the default, and it is a no-op for a single sample -- but it
    was surfaced as a question whose only answer was the value just rejected, so
    answering it re-opened it forever."""
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
    """Ordering within a pass cannot help when the override's param is deferred:
    the guess is already bound by the time it is considered, so it must be
    evicted and re-deduced."""
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
    """With nothing pinned, "enriched in female adults" must bind
    comparator=female and reference=male. WDK computes fold change as
    comparator-vs-reference, so the reverse searches for MALE-enriched genes --
    a plausible, non-empty, silently wrong answer."""
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
    """Two explicit picks that collide are the user's stated intent. Honor both
    rather than silently rewriting one of them."""

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
    """With three options, freeing one still leaves a real choice -- deducing
    would be a guess, so the evicted param becomes a question."""
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
    """Eviction must not cascade into a pair collapsing onto one value."""
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
    """Each override wants the value the other guess holds. Resolution must
    settle rather than evicting back and forth until the depth cap."""

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
    """Nothing may be silently dropped: an evicted param must come back as a
    binding or as an open slot, never vanish."""
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
    """``min_max_avg_ref``/``_comp`` choose HOW to collapse replicates on each
    side, not WHICH samples the side contains. Averaging both sides is the
    normal configuration, so the degenerate-pair rule must not strand one of
    them -- WDK labels them "Operation Applied to Reference Samples", which
    mentions samples without selecting any."""
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
