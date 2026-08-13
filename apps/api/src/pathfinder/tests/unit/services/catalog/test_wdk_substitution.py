"""WDK reports which values it supplied, and that report outranks ours."""

from __future__ import annotations

from pathfinder.domain.parameters.values import NumberValue, SinglePickValue
from pathfinder.services.catalog.wdk_substitution import substituted_params


class TestWhatWDKFilledIn:
    def test_a_param_we_did_not_send_is_substituted(self) -> None:
        filled = substituted_params(
            sent={"organism": SinglePickValue(value="Pf")},
            echoed={"organism": "Pf", "min_weight": "10000"},
        )

        assert filled == ["min_weight"]

    def test_a_param_we_sent_is_not_substituted(self) -> None:
        filled = substituted_params(
            sent={"organism": SinglePickValue(value="Pf")},
            echoed={"organism": "Pf"},
        )

        assert filled == []

    def test_a_value_wdk_replaced_counts_as_substituted(self) -> None:
        # An unknown term comes back as the empty selection, which is WDK
        # choosing a value rather than accepting ours.
        filled = substituted_params(
            sent={"organism": SinglePickValue(value="Nonexistent")},
            echoed={"organism": "[]"},
        )

        assert filled == ["organism"]

    def test_an_unchanged_numeric_is_not_substituted(self) -> None:
        filled = substituted_params(
            sent={"fold_change": NumberValue(value=2)},
            echoed={"fold_change": "2"},
        )

        assert filled == []


class TestItIsOrderIndependent:
    def test_results_are_sorted(self) -> None:
        filled = substituted_params(
            sent={},
            echoed={"b": "1", "a": "2"},
        )

        assert filled == ["a", "b"]

    def test_an_echoed_empty_value_is_not_a_substitution(self) -> None:
        # WDK omits a value it has nothing to offer for; an empty string is not
        # a choice it made.
        filled = substituted_params(sent={}, echoed={"a": ""})

        assert filled == []
