"""Swapping the organism re-reads every parameter that hangs off it.

The dependent's vocabulary is only meaningful under its parents, so a
substitution resolves the child at the new context rather than carrying the old
value forward.
"""

from __future__ import annotations

from collections.abc import Callable

from pathfinder.domain.parameters.values import SinglePickValue, to_wire
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_dag import resolve_params_with_intent
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_intent import ParamIntent

_PF = "Plasmodium falciparum 3D7"
_PV = "Plasmodium vivax P01"

_PF_PROFILESETS = [
    VocabOption(value="DeRisi 3D7 Smoothed", display="DeRisi 3D7 Smoothed"),
    VocabOption(value="Su 3D7 strand-specific", display="Su 3D7 strand-specific"),
]
_PV_PROFILESETS = [VocabOption(value="Zhu P01 time course", display="Zhu P01")]


def _organism() -> ParameterInfo:
    return ParameterInfo(
        name="organism",
        display_name="Organism",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        vocab_leaves=[
            VocabOption(value=_PF, display="P. falciparum 3D7"),
            VocabOption(value=_PV, display="P. vivax P01"),
        ],
    )


def _profileset(options: list[VocabOption], default: str | None) -> ParameterInfo:
    return ParameterInfo(
        name="profileset",
        display_name="Profile set",
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        allowed_values=options,
        vocab_depends_on=["organism"],
    )


def _under(context: dict[str, str]) -> list[ParameterInfo]:
    """The search as WDK renders it for the organism in context."""
    chosen = context.get("organism", "")
    if _PV in chosen:
        return [_organism(), _profileset(_PV_PROFILESETS, "Zhu P01 time course")]
    return [_organism(), _profileset(_PF_PROFILESETS, "DeRisi 3D7 Smoothed")]


def _empty_under_vivax(context: dict[str, str]) -> list[ParameterInfo]:
    """The dependent has nothing to offer once the new organism is bound."""
    if _PV in context.get("organism", ""):
        return [_organism(), _profileset([], None)]
    return [_organism(), _profileset(_PF_PROFILESETS, "DeRisi 3D7 Smoothed")]


ParamsAt = Callable[[dict[str, str]], list[ParameterInfo]]


async def _resolve(
    at: ParamsAt, overrides: dict[str, str | list[str]]
) -> tuple[dict[str, str], list[str]]:
    async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
        return at(context)

    resolved = await resolve_params_with_intent(
        fetch_at=fetch_at,
        intent=ParamIntent(text="expression profile of the protease genes"),
        overrides=overrides,
    )
    return (
        {name: to_wire(value) for name, value in resolved.params.items()},
        [slot.param_name for slot in resolved.open_slots],
    )


async def test_the_dependent_is_read_under_the_new_parent() -> None:
    params, slots = await _resolve(_under, {"organism": [_PV]})

    assert params["profileset"] == "Zhu P01 time course"
    assert slots == []


async def test_the_old_parents_default_is_not_carried_into_the_new_one() -> None:
    """The default the previous organism supplied names no entry under the new one."""
    before, _ = await _resolve(_under, {"organism": [_PF]})
    after, _ = await _resolve(_under, {"organism": [_PV]})

    assert before["profileset"] == "DeRisi 3D7 Smoothed"
    assert after["profileset"] != before["profileset"]


async def test_a_dependent_with_no_entry_under_the_new_parent_is_an_open_slot() -> None:
    """A parameter with nothing to choose is asked, never silently defaulted."""
    params, slots = await _resolve(_empty_under_vivax, {"organism": [_PV]})

    assert "profileset" not in params
    assert slots == ["profileset"]


async def test_the_untouched_parent_still_binds_what_the_request_states() -> None:
    params, _ = await _resolve(_under, {"organism": [_PV]})

    assert params["organism"] == '["Plasmodium vivax P01"]'
    assert (
        SinglePickValue(value="Zhu P01 time course").to_wire() == params["profileset"]
    )
