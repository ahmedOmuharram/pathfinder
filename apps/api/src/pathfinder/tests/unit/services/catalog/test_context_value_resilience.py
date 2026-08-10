"""Loading a step's parameter form must survive bad stored values.

``expand_search_details_with_params`` is a READ: it feeds the editor's
parameter form, passing the step's saved values as context so WDK echoes
them back. When one saved value no longer matches its vocabulary, failing
the whole request makes the step editor impossible to open - the user
cannot even reach the field to correct it. One unusable context value is
dropped instead, so the form still loads.

Mutations keep validating strictly; this leniency is scoped to the read.
"""

from pathfinder.domain.parameters.values import (
    MultiPickValue,
    ParamValue,
    StringValue,
)
from pathfinder.services.catalog.param_resolution import drop_unusable_context_values


def test_keeps_values_that_canonicalize() -> None:
    context: dict[str, ParamValue] = {
        "organism": MultiPickValue(values=["Plasmodium falciparum 3D7"])
    }

    def canonicalize(values: dict[str, ParamValue]) -> dict[str, ParamValue]:
        return values

    assert drop_unusable_context_values(context, canonicalize) == context


def test_drops_only_the_offending_value() -> None:
    good = MultiPickValue(values=["Plasmodium falciparum 3D7"])
    bad = MultiPickValue(values=["[]"])
    context: dict[str, ParamValue] = {"organism": good, "phyletic_term_map": bad}

    def canonicalize(values: dict[str, ParamValue]) -> dict[str, ParamValue]:
        if "phyletic_term_map" in values:
            msg = "Parameter 'phyletic_term_map' does not accept '[]'."
            raise ValueError(msg)
        return values

    assert drop_unusable_context_values(context, canonicalize) == {"organism": good}


def test_returns_empty_when_every_value_is_unusable() -> None:
    context: dict[str, ParamValue] = {
        "a": StringValue(value="x"),
        "b": StringValue(value="y"),
    }

    def canonicalize(values: dict[str, ParamValue]) -> dict[str, ParamValue]:
        if values:
            msg = "all bad"
            raise ValueError(msg)
        return values

    assert drop_unusable_context_values(context, canonicalize) == {}


def test_empty_context_is_returned_unchanged() -> None:
    def canonicalize(values: dict[str, ParamValue]) -> dict[str, ParamValue]:
        return values

    assert drop_unusable_context_values({}, canonicalize) == {}
