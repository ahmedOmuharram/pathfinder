"""What a record carries.

``recordClassName`` names two different things in one response body, and an
attribute value is a string, an object, or null.
"""

from __future__ import annotations

from typing import Any

from pathfinder.integrations.veupathdb.wdk_models import WDKAnswer

_LINK: dict[str, str] = {
    "url": "/a/app/record/gene/PF3D7_0100100",
    "displayText": "PF3D7_0100100",
}

_ANSWER: dict[str, Any] = {
    "meta": {
        "totalCount": 1,
        "responseCount": 1,
        "recordClassName": "transcript",
    },
    "records": [
        {
            "displayName": "PF3D7_0100100",
            "id": [{"name": "source_id", "value": "PF3D7_0100100"}],
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "attributes": {
                "source_id": "PF3D7_0100100",
                "gene_link": _LINK,
                "product": None,
                "organism": "<i>Plasmodium falciparum</i> 3D7",
                "empty_link": {"url": "/a/app/record/gene/x", "displayText": ""},
            },
        }
    ],
}


def _answer() -> WDKAnswer:
    return WDKAnswer.model_validate(_ANSWER)


class TestTheTwoRecordClassNames:
    def test_meta_carries_the_url_segment(self) -> None:
        assert _answer().meta.record_class_name == "transcript"

    def test_a_record_carries_the_full_name(self) -> None:
        record = _answer().records[0]

        assert (
            record.record_class_name == "TranscriptRecordClasses.TranscriptRecordClass"
        )

    def test_one_is_not_the_other(self) -> None:
        answer = _answer()

        assert answer.meta.record_class_name != answer.records[0].record_class_name


class TestAnAttributeValueIsNotAlwaysAString:
    def test_a_plain_value_is_a_string(self) -> None:
        assert _answer().records[0].attributes["source_id"] == "PF3D7_0100100"

    def test_a_link_value_stays_an_object(self) -> None:
        # The url is what a reader clicks, so it must survive to the client.
        assert _answer().records[0].attributes["gene_link"] == _LINK

    def test_an_absent_value_is_null(self) -> None:
        assert _answer().records[0].attributes["product"] is None

    def test_markup_is_not_stripped(self) -> None:
        assert "<i>" in str(_answer().records[0].attributes["organism"])


class TestComparingAnAttributeToText:
    def test_a_plain_value_compares_by_itself(self) -> None:
        assert _answer().records[0].attribute_text("source_id") == "PF3D7_0100100"

    def test_a_link_value_compares_by_its_display_text(self) -> None:
        assert _answer().records[0].attribute_text("gene_link") == "PF3D7_0100100"

    def test_a_null_value_has_no_text(self) -> None:
        assert _answer().records[0].attribute_text("product") is None

    def test_a_link_without_display_text_has_no_text(self) -> None:
        assert _answer().records[0].attribute_text("empty_link") is None

    def test_an_attribute_that_was_not_requested_has_no_text(self) -> None:
        assert _answer().records[0].attribute_text("molecular_weight") is None
