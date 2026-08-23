"""The literal string each parameter kind puts in ``searchConfig.parameters``.

A round trip constrains the codec. These constrain the wire form, which is
what WDK reads.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError as PydanticValidationError

from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.domain.parameters.values import (
    DateRangeValue,
    DateValue,
    FilterTermClause,
    FilterValue,
    InputDatasetValue,
    InputStepValue,
    MultiPickValue,
    NumberRangeValue,
    NumberValue,
    ParamValue,
    SinglePickValue,
    StringValue,
    TimestampValue,
    wire_map,
)
from pathfinder.domain.parameters.wdk_vocab import vocab_keys
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchResponse

_ONE_OF_EVERY_KIND: dict[str, ParamValue] = {
    "a_string": StringValue(value="kinase"),
    "a_number": NumberValue(value=42),
    "a_number_range": NumberRangeValue(min=1, max=2),
    "a_date": DateValue(value="2026-01-01"),
    "a_date_range": DateRangeValue(min="2026-01-01", max="2026-12-31"),
    "a_timestamp": TimestampValue(value="1766000000000"),
    "a_single_pick": SinglePickValue(value="Gene"),
    "a_multi_pick": MultiPickValue(values=["product", "name"]),
    "a_filter": FilterValue(filters=[FilterTermClause(field="organism")]),
    "an_input_dataset": InputDatasetValue(dataset_id="558341"),
    "an_input_step": InputStepValue(step_id="440085983"),
}


class TestWdkParam002EveryValueIsAString:
    """WDK-PARAM-002: the structured kinds are stringified into the map."""

    def test_wdk_param_002_every_kind_encodes_to_a_string(self) -> None:
        encoded = wire_map(_ONE_OF_EVERY_KIND)

        assert [type(v) for v in encoded.values()] == [str] * len(_ONE_OF_EVERY_KIND)

    def test_wdk_param_002_the_structured_kinds_carry_json_in_the_string(self) -> None:
        encoded = wire_map(_ONE_OF_EVERY_KIND)

        assert json.loads(encoded["a_number_range"]) == {"min": 1, "max": 2}
        assert json.loads(encoded["a_date_range"]) == {
            "min": "2026-01-01",
            "max": "2026-12-31",
        }
        assert json.loads(encoded["a_multi_pick"]) == ["product", "name"]
        assert json.loads(encoded["a_filter"])["filters"][0]["field"] == "organism"

    def test_wdk_param_002_a_json_object_is_never_nested_in_the_map(self) -> None:
        # A map value that is an object rather than a string is a 400 from the
        # properties parser, which reads every value with getString.
        encoded = wire_map(_ONE_OF_EVERY_KIND)

        assert json.loads(json.dumps(encoded)) == encoded


class TestWdkParam003SinglePickIsABareTerm:
    """WDK-PARAM-003: a bare term, never an array, never quoted."""

    def test_wdk_param_003_a_single_pick_wire_value_is_the_bare_term(self) -> None:
        assert SinglePickValue(value="Gene").to_wire() == "Gene"

    def test_wdk_param_003_a_single_pick_is_not_json_encoded(self) -> None:
        # `["Gene"]` means the same thing to WDK; `"Gene"` with quotes does not.
        wire = SinglePickValue(value="Gene").to_wire()

        assert not wire.startswith(("[", '"'))

    def test_wdk_param_003_a_term_containing_a_comma_survives_intact(self) -> None:
        # Single-pick does not split on commas, and `2,-3` is a real term.
        assert SinglePickValue(value="2,-3").to_wire() == "2,-3"

    def test_wdk_param_003_two_terms_are_not_expressible(self) -> None:
        # Two elements is an unhandled WdkRuntimeException, so the type holds one.
        with pytest.raises(PydanticValidationError):
            SinglePickValue(value=["Gene", "Transcript"])  # type: ignore[arg-type]

    def test_wdk_param_003_the_wire_value_is_one_of_the_declared_terms(self) -> None:
        search = WDKSearchResponse.model_validate(
            load_recorded("search_genes_by_exon_count").json_body()
        ).search_data
        scope = next(p for p in search.parameters or [] if p.name == "scope")

        assert scope.type == "single-pick-vocabulary"
        assert vocab_keys(scope.vocabulary) == {"Gene", "Transcript"}
        assert SinglePickValue(value="Gene").to_wire() in vocab_keys(scope.vocabulary)


class TestWdkParam009HandlesAreBareIssuedIds:
    """WDK-PARAM-009: an input value is an id WDK issued, sent bare."""

    def test_wdk_param_009_an_input_step_wire_value_is_the_bare_id(self) -> None:
        assert InputStepValue(step_id="440085983").to_wire() == "440085983"

    def test_wdk_param_009_an_input_step_id_is_read_back_by_long_parse_long(
        self,
    ) -> None:
        wire = InputStepValue(step_id="440085983").to_wire()

        assert int(wire) == 440085983

    def test_wdk_param_009_an_input_dataset_wire_value_is_the_bare_id(self) -> None:
        assert InputDatasetValue(dataset_id="558341").to_wire() == "558341"

    def test_wdk_param_009_neither_handle_is_json_encoded(self) -> None:
        assert InputStepValue(step_id="7").to_wire() == "7"
        assert InputDatasetValue(dataset_id="7").to_wire() == "7"

    def test_wdk_param_009_an_empty_handle_is_not_expressible(self) -> None:
        # Empty is what WDK reports before a wiring, and it is WDK's to write.
        with pytest.raises(PydanticValidationError):
            InputStepValue(step_id="")
        with pytest.raises(PydanticValidationError):
            InputDatasetValue(dataset_id="")
