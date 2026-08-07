"""Contrast semantics: which sample group is the baseline, and which direction.

WDK states the rule plainly in ``regulated_dir``'s help:

    "Select 'up-regulated' to find genes that have higher expression in the
     COMPARATOR as compared to the REFERENCE."

So "genes enriched in female adults" must bind comparator=female,
reference=male. A live run bound the inverse (reference=female,
comparison=male) and asked for "up or down regulated", which searches for
male-enriched genes in both directions.

This class of bug is worse than the zero-result ones: an inverted contrast
returns a plausible, non-empty gene set that is confidently the wrong biology,
with nothing to signal it. Both defects are pinned here.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.values import MultiPickValue, SinglePickValue
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.integrations.embeddings.prefixes import SEARCH_QUERY_PREFIX
from pathfinder.services.catalog.param_dag import (
    ParameterInfo,
    ParamFetcher,
    resolve_params_with_intent,
)
from pathfinder.services.catalog.param_intent import ParamIntent

SEXES = [
    VocabOption(value="male", display="male"),
    VocabOption(value="female", display="female"),
]
# Verified against VectorBase GSE22339; note "up" is a substring of the
# both-directions option, which is what made the bare-token match go wrong.
DIRECTIONS = [
    VocabOption(value="down-regulated", display="down-regulated"),
    VocabOption(value="up or down regulated", display="up or down regulated"),
    VocabOption(value="up-regulated", display="up-regulated"),
]


def _p(
    name: str,
    display: str,
    allowed: list[VocabOption],
    default: str | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=display,
        type="multi-pick-vocabulary" if "samples" in name else "single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        allowed_values=allowed,
    )


async def _embed_prefers_female(texts: Sequence[str]) -> list[list[float]]:
    return [
        [1.0, 0.0] if t.startswith(SEARCH_QUERY_PREFIX) or "female" in t else [0.0, 1.0]
        for t in texts
    ]


def _fold_change_fetch() -> ParamFetcher:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        # Reference is listed FIRST, as WDK returns it -- the slot-agnostic
        # matcher therefore reached it first and gave it the subject.
        return [
            _p("samples_fc_ref_generic", "Reference Samples", SEXES),
            _p("samples_fc_comp_generic", "Comparison Samples", SEXES),
            _p(
                "regulated_dir",
                "Direction",
                DIRECTIONS,
                default="up or down regulated",
            ),
        ]

    return fetch_at


async def _resolve(text: str, direction: str | None = "up"):
    return await resolve_params_with_intent(
        fetch_at=_fold_change_fetch(),
        intent=ParamIntent(
            organism_scope="Aedes aegypti", text=text, direction_hint=direction
        ),
        embed=_embed_prefers_female,
    )


def _values(param: object) -> list[str]:
    if isinstance(param, MultiPickValue):
        return list(param.values)
    if isinstance(param, SinglePickValue):
        return [param.value]
    msg = f"unexpected param value: {param!r}"
    raise AssertionError(msg)


@pytest.mark.asyncio
async def test_the_enriched_group_becomes_the_comparator_not_the_reference() -> None:
    rp = await _resolve("genes enriched in female adults versus male adults")
    comp = rp.params.get("samples_fc_comp_generic")
    assert comp is not None, "comparison slot left unbound"
    assert _values(comp) == ["female"], (
        "the group the user wants enriched must be the COMPARATOR; binding it "
        "as the reference inverts the biology"
    )


@pytest.mark.asyncio
async def test_the_baseline_becomes_the_reference() -> None:
    rp = await _resolve("genes enriched in female adults versus male adults")
    ref = rp.params.get("samples_fc_ref_generic")
    assert ref is not None, "reference slot left unbound"
    assert _values(ref) == ["male"]


@pytest.mark.asyncio
async def test_direction_hint_is_not_swallowed_by_the_both_directions_option() -> None:
    """``match_option(opts, "up")`` substring-hits "up or down regulated",
    silently dropping the directional filter."""
    rp = await _resolve("genes upregulated in female adults", direction="up")
    direction = rp.params.get("regulated_dir")
    assert direction is not None
    assert _values(direction) == ["up-regulated"], (
        f"direction hint lost: bound {_values(direction)}"
    )


@pytest.mark.asyncio
async def test_down_direction_binds_the_down_option() -> None:
    rp = await _resolve("genes downregulated in female adults", direction="down")
    direction = rp.params["regulated_dir"]
    assert _values(direction) == ["down-regulated"]


@pytest.mark.asyncio
async def test_no_direction_hint_keeps_the_wdk_both_directions_default() -> None:
    """Absent an intent, WDK's own default is the honest choice -- inventing a
    direction would filter out half the answer without being asked to."""
    rp = await _resolve("genes in female adults", direction=None)
    direction = rp.params["regulated_dir"]
    assert _values(direction) == ["up or down regulated"]


@pytest.mark.asyncio
async def test_an_explicit_override_still_wins_over_the_role_rule() -> None:
    rp = await resolve_params_with_intent(
        fetch_at=_fold_change_fetch(),
        intent=ParamIntent(
            organism_scope=None,
            text="genes enriched in female adults",
            direction_hint="up",
        ),
        embed=_embed_prefers_female,
        overrides={
            "samples_fc_ref_generic": "female",
            "samples_fc_comp_generic": "male",
        },
    )
    assert _values(rp.params["samples_fc_ref_generic"]) == ["female"]
    assert _values(rp.params["samples_fc_comp_generic"]) == ["male"]


@pytest.mark.asyncio
async def test_the_pair_is_never_degenerate() -> None:
    rp = await _resolve("genes enriched in female adults")
    ref = rp.params.get("samples_fc_ref_generic")
    comp = rp.params.get("samples_fc_comp_generic")
    if ref is not None and comp is not None:
        assert _values(ref) != _values(comp)


@pytest.mark.asyncio
async def test_a_group_named_verbatim_binds_the_comparator_without_embeddings() -> None:
    """A vocabulary term appearing literally in the criterion text is far
    stronger evidence than a similarity score. Live, the real embedding of
    "upregulated in adult female versus adult male" scores BOTH "male" and
    "female" below the semantic floor, so the contrast could not resolve at all
    -- while the answer was sitting in the text. Longest match wins, so "female"
    beats the "male" contained inside it.
    """

    async def _embed_matches_nothing(texts: Sequence[str]) -> list[list[float]]:
        return [
            [1.0, 0.0] if t.startswith(SEARCH_QUERY_PREFIX) else [0.0, 1.0]
            for t in texts
        ]

    rp = await resolve_params_with_intent(
        fetch_at=_fold_change_fetch(),
        intent=ParamIntent(
            organism_scope="Aedes aegypti",
            text="OBP genes upregulated in adult female versus adult male",
            direction_hint="up",
        ),
        embed=_embed_matches_nothing,
    )
    assert _values(rp.params["samples_fc_comp_generic"]) == ["female"]
    assert _values(rp.params["samples_fc_ref_generic"]) == ["male"]
