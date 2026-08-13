"""A vocabulary read without parents names the defaults it was read under."""

from __future__ import annotations

from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.domain.parameters.wdk_vocab import (
    WDKTreeBoxVocabNode,
    WDKVocabNodeData,
)
from pathfinder.integrations.veupathdb.wdk_parameters import WDKEnumParam
from pathfinder.services.catalog.param_formatting import format_typed_param

_DEPENDS = {"samples": ["profileset"]}


def _samples() -> WDKEnumParam:
    return WDKEnumParam(
        name="samples",
        displayName="Samples",
        type="multi-pick-vocabulary",
        vocabulary=WDKTreeBoxVocabNode(
            data=WDKVocabNodeData(term="root", display="root"),
            children=[
                WDKTreeBoxVocabNode(
                    data=WDKVocabNodeData(term="20 Hour", display="20 Hour")
                )
            ],
        ),
    )


class TestAnUnqualifiedRead:
    def test_the_note_names_the_parent_value_wdk_used(self) -> None:
        info = format_typed_param(
            _samples(),
            _DEPENDS,
            {},
            parent_defaults={"profileset": "DeRisi HB3 Smoothed"},
        )

        assert info.note is not None
        assert "DeRisi HB3 Smoothed" in info.note

    def test_it_warns_that_another_parent_gives_another_list(self) -> None:
        info = format_typed_param(
            _samples(),
            _DEPENDS,
            {},
            parent_defaults={"profileset": "DeRisi HB3 Smoothed"},
        )

        assert info.note is not None
        assert "DIFFERENT" in info.note

    def test_without_a_known_default_it_still_says_it_is_a_default(self) -> None:
        info = format_typed_param(_samples(), _DEPENDS, {})

        assert info.note is not None
        assert "default" in info.note.lower()


class TestAQualifiedRead:
    def test_an_applied_context_still_names_what_was_applied(self) -> None:
        info = format_typed_param(
            _samples(),
            _DEPENDS,
            {},
            applied_context={
                "profileset": SinglePickValue(value="DeRisi 3D7 Smoothed")
            },
            parent_defaults={"profileset": "DeRisi HB3 Smoothed"},
        )

        assert info.note is not None
        assert "DeRisi 3D7 Smoothed" in info.note
        assert "DeRisi HB3 Smoothed" not in info.note
