"""Contrast semantics: which sample group is the baseline, and which direction.

WDK states the rule plainly in ``regulated_dir``'s help:

    "Select 'up-regulated' to find genes that have higher expression in the
     COMPARATOR as compared to the REFERENCE."

So a criterion about genes enriched in female adults binds comparator=female,
reference=male. An inverted contrast returns a plausible, non-empty gene set
that is confidently the wrong biology, with nothing to signal it.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import MultiPickValue, SinglePickValue
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_dag import (
    OverrideMap,
    ParameterInfo,
    ParamFetcher,
    ResolvedParams,
    resolve_params_with_intent,
)
from pathfinder.services.catalog.param_intent import ParamIntent

SEXES = [
    VocabOption(value="male", display="male"),
    VocabOption(value="female", display="female"),
]
# Verified against VectorBase GSE22339; note "up" is a substring of the
# both-directions option.
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


def _fold_change_fetch() -> ParamFetcher:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        del context
        # Reference is listed FIRST, as WDK returns it.
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


async def _resolve(overrides: OverrideMap | None = None) -> ResolvedParams:
    return await resolve_params_with_intent(
        fetch_at=_fold_change_fetch(),
        intent=ParamIntent(),
        overrides=overrides,
    )


def _values(param: object) -> list[str]:
    if isinstance(param, MultiPickValue):
        return list(param.values)
    if isinstance(param, SinglePickValue):
        return [param.value]
    msg = f"unexpected param value: {param!r}"
    raise AssertionError(msg)


@pytest.mark.asyncio
async def test_the_baseline_becomes_the_group_the_comparator_did_not_take() -> None:
    """Only the comparator is stated. The reference is what is left, and taking
    it the other way round inverts the biology."""
    rp = await _resolve({"samples_fc_comp_generic": "female"})

    comp = rp.params.get("samples_fc_comp_generic")
    ref = rp.params.get("samples_fc_ref_generic")
    assert comp is not None, "comparison slot left unbound"
    assert ref is not None, "reference slot left unbound"
    assert _values(comp) == ["female"]
    assert _values(ref) == ["male"]


@pytest.mark.asyncio
async def test_a_stated_direction_is_not_swallowed_by_the_both_directions_option() -> (
    None
):
    """A substring of the both-directions label must not silently replace it."""
    rp = await _resolve(
        {"samples_fc_comp_generic": "female", "regulated_dir": "up-regulated"}
    )
    direction = rp.params.get("regulated_dir")
    assert direction is not None
    assert _values(direction) == ["up-regulated"], (
        f"direction lost: bound {_values(direction)}"
    )


@pytest.mark.asyncio
async def test_no_stated_direction_keeps_the_wdk_both_directions_default() -> None:
    """Absent a statement, WDK's own default is the honest choice -- inventing a
    direction would filter out half the answer without being asked to."""
    rp = await _resolve({"samples_fc_comp_generic": "female"})
    direction = rp.params["regulated_dir"]
    assert _values(direction) == ["up or down regulated"]


@pytest.mark.asyncio
async def test_both_sides_stated_are_honored_verbatim() -> None:
    rp = await _resolve(
        {
            "samples_fc_ref_generic": "female",
            "samples_fc_comp_generic": "male",
        }
    )
    assert _values(rp.params["samples_fc_ref_generic"]) == ["female"]
    assert _values(rp.params["samples_fc_comp_generic"]) == ["male"]


@pytest.mark.asyncio
async def test_the_pair_is_never_degenerate() -> None:
    rp = await _resolve({"samples_fc_comp_generic": "female"})
    ref = rp.params.get("samples_fc_ref_generic")
    comp = rp.params.get("samples_fc_comp_generic")
    if ref is not None and comp is not None:
        assert _values(ref) != _values(comp)


@pytest.mark.asyncio
async def test_an_unstated_pair_is_asked_about_rather_than_guessed() -> None:
    rp = await _resolve()
    assert "samples_fc_comp_generic" not in rp.params
    assert {s.param_name for s in rp.open_slots} >= {
        "samples_fc_ref_generic",
        "samples_fc_comp_generic",
    }
