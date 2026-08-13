"""Reads which parameter values WDK supplied rather than accepted."""

from __future__ import annotations

from collections.abc import Mapping

from pathfinder.domain.parameters.values import ParamValue, to_wire


def substituted_params(
    *,
    sent: Mapping[str, ParamValue],
    echoed: Mapping[str, str],
) -> list[str]:
    """Params whose echoed value is WDK's rather than the caller's."""
    sent_wire = {name: to_wire(value) for name, value in sent.items()}
    return sorted(
        name for name, value in echoed.items() if value and sent_wire.get(name) != value
    )
