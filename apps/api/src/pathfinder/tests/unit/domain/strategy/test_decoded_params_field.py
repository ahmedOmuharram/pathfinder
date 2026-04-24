"""Tests for the DecodedParamsField BeforeValidator and decode_wire_dict.

These guard the SSOT for parameter-shape decoding. Every entry point that
holds parameter values uses ``DecodedParamsField`` so wire-form strings
(JSON-encoded lists/objects from legacy DB rows, frontend echoes, or
LLM emissions) always become native Python types before any business
logic touches them.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field, ValidationError

from pathfinder.domain.strategy.types import (
    DecodedParamsField,
    decode_wire_dict,
    decode_wire_value,
)


class _Holder(BaseModel):
    """Test fixture model that uses the canonical Annotated type."""

    parameters: DecodedParamsField = Field(default_factory=dict)


class TestDecodeWireValue:
    def test_native_list_passes_through(self) -> None:
        assert decode_wire_value(["Plasmodium"]) == ["Plasmodium"]

    def test_json_encoded_list_string_decodes(self) -> None:
        assert decode_wire_value('["Plasmodium"]') == ["Plasmodium"]

    def test_json_encoded_object_string_decodes(self) -> None:
        assert decode_wire_value('{"min": 1, "max": 5}') == {"min": 1, "max": 5}

    def test_bare_string_passes_through(self) -> None:
        assert decode_wire_value("Plasmodium") == "Plasmodium"

    def test_numeric_string_passes_through(self) -> None:
        assert decode_wire_value("42") == "42"

    def test_int_passes_through(self) -> None:
        assert decode_wire_value(42) == 42

    def test_malformed_json_string_passes_through(self) -> None:
        assert decode_wire_value('["unclosed') == '["unclosed'

    def test_empty_string_passes_through(self) -> None:
        assert decode_wire_value("") == ""

    def test_none_passes_through(self) -> None:
        assert decode_wire_value(None) is None


class TestDecodeWireDict:
    def test_decodes_each_value(self) -> None:
        result = decode_wire_dict(
            {"organism": '["Plasmodium"]', "go_term": "GO:0016301"},
        )
        assert result == {"organism": ["Plasmodium"], "go_term": "GO:0016301"}

    def test_passes_through_non_dict(self) -> None:
        assert decode_wire_dict("not a dict") == "not a dict"
        assert decode_wire_dict(None) is None
        assert decode_wire_dict(42) == 42

    def test_empty_dict(self) -> None:
        assert decode_wire_dict({}) == {}


class TestDecodedParamsFieldBeforeValidator:
    """The validator runs on every model_validate, so HTTP requests, DB
    loads, and tool calls all benefit equally."""

    def test_native_list_value_kept(self) -> None:
        h = _Holder.model_validate({"parameters": {"organism": ["Plasmodium"]}})
        assert h.parameters == {"organism": ["Plasmodium"]}

    def test_wire_string_decoded_to_list(self) -> None:
        h = _Holder.model_validate(
            {"parameters": {"organism": '["Plasmodium"]'}},
        )
        assert h.parameters == {"organism": ["Plasmodium"]}

    def test_wire_string_decoded_to_dict(self) -> None:
        h = _Holder.model_validate(
            {"parameters": {"age_range": '{"min": 18, "max": 80}'}},
        )
        assert h.parameters == {"age_range": {"min": 18, "max": 80}}

    def test_mixed_payload_decodes_per_value(self) -> None:
        h = _Holder.model_validate(
            {
                "parameters": {
                    "organism": '["Plasmodium"]',
                    "go_term": "GO:0016301",
                    "go_term_evidence": '["Curated", "Computed"]',
                    "go_term_slim": "No",
                },
            },
        )
        assert h.parameters == {
            "organism": ["Plasmodium"],
            "go_term": "GO:0016301",
            "go_term_evidence": ["Curated", "Computed"],
            "go_term_slim": "No",
        }

    def test_non_dict_parameters_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _Holder.model_validate({"parameters": "not a dict"})

    def test_default_empty(self) -> None:
        h = _Holder.model_validate({})
        assert h.parameters == {}
