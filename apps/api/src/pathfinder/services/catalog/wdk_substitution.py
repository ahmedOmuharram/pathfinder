"""Reads which parameter values WDK supplied rather than accepted."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import TypeAdapter, ValidationError

from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import ParamValue, to_wire

_VOCABULARY_TYPES = frozenset(
    {"single-pick-vocabulary", "multi-pick-vocabulary"},
)

_SELECTION_ADAPTER: TypeAdapter[list[str]] = TypeAdapter(list[str])


def _selection(wire: str) -> frozenset[str]:
    """The values a vocabulary wire form selects, order and encoding aside."""
    if not wire:
        return frozenset()
    try:
        return frozenset(_SELECTION_ADAPTER.validate_json(wire))
    except ValidationError:
        return frozenset({wire})


def _is_vocabulary(spec: ParamSpecNormalized | None) -> bool:
    return spec is not None and spec.param_type in _VOCABULARY_TYPES


def substituted_params(
    *,
    sent: Mapping[str, ParamValue],
    echoed: Mapping[str, str],
    specs: Mapping[str, ParamSpecNormalized],
    values_were_read: bool,
) -> list[str]:
    """Params whose echoed value is WDK's rather than the caller's.

    A definition WDK built without reading the caller's values describes no
    caller at all, so only the params left unset are read from it.
    """
    sent_wire = {name: to_wire(value) for name, value in sent.items()}
    supplied: list[str] = []
    for name, echoed_value in echoed.items():
        vocabulary = _is_vocabulary(specs.get(name))
        ours = sent_wire.get(name)
        if ours is None:
            selects_nothing = (
                not _selection(echoed_value) if vocabulary else not echoed_value
            )
            if not selects_nothing:
                supplied.append(name)
            continue
        if not values_were_read:
            continue
        differs = (
            _selection(ours) != _selection(echoed_value)
            if vocabulary
            else ours != echoed_value
        )
        if differs:
            supplied.append(name)
    return sorted(supplied)
