"""Tests for custom CamelModel base class and RoundedFloat types.

These are PathFinder's custom Pydantic infrastructure — alias generation
and float rounding. Everything else (model_dump, model_validate, nested
models, optional fields) is Pydantic's responsibility.
"""

from veupath_chatbot.platform.pydantic_base import (
    CamelModel,
    RoundedFloat,
    RoundedFloat2,
)

# ---------------------------------------------------------------------------
# Test-only models
# ---------------------------------------------------------------------------


class _MultiWord(CamelModel):
    required_field: str = ""
    optional_str: str | None = None
    some_long_name: int = 0


class _WithRounding(CamelModel):
    rounded_4: RoundedFloat = 0.0
    rounded_2: RoundedFloat2 = 0.0
    plain: float = 0.0


# ---------------------------------------------------------------------------
# CamelModel: snake_case -> camelCase alias generation
# ---------------------------------------------------------------------------


class TestCamelCaseAliases:
    def test_multi_word_fields_become_camel_case(self) -> None:
        obj = _MultiWord(required_field="yes", optional_str="maybe", some_long_name=42)
        j = obj.model_dump(by_alias=True)
        assert "requiredField" in j
        assert "optionalStr" in j
        assert "someLongName" in j

    def test_camel_case_input_accepted(self) -> None:
        obj = _MultiWord.model_validate(
            {"requiredField": "yes", "optionalStr": "maybe", "someLongName": 42}
        )
        assert obj.required_field == "yes"
        assert obj.some_long_name == 42


# ---------------------------------------------------------------------------
# RoundedFloat / RoundedFloat2: custom rounding on serialization
# ---------------------------------------------------------------------------


class TestRoundedFloat:
    def test_rounding_precision(self) -> None:
        obj = _WithRounding(
            rounded_4=3.14159265,
            rounded_2=3.14159265,
            plain=3.14159265,
        )
        j = obj.model_dump(by_alias=True)
        assert j["rounded4"] == 3.1416  # RoundedFloat: 4 decimals
        assert j["rounded2"] == 3.14  # RoundedFloat2: 2 decimals
        assert j["plain"] == 3.14159265  # plain float: untouched
