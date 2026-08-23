"""``decode(encode(x)) == x`` for every parameter value.

Values cross the wire boundary on every step read and every step write, and
the two directions were never checked against each other. That is how an
empty multi-pick came to be written as the literal string ``"[]"`` and read
back as a vocabulary term named ``[]`` - which WDK then rejected on a
parameter whose own spec allows an empty value.

Generated cases rather than examples, because the failures here are the
values nobody thinks to write down: the empty selection, a term containing
the separator, a lone minus sign.
"""

from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from pathfinder.domain.parameters.values import (
    DateRangeValue,
    DateValue,
    FilterValue,
    InputDatasetValue,
    InputStepValue,
    MultiPickValue,
    NumberRangeValue,
    NumberValue,
    ParamKind,
    ParamValue,
    SinglePickValue,
    StringValue,
    TimestampValue,
)
from pathfinder.integrations.veupathdb.value_decoding import (
    decode_params,
    encode_params,
)


def _round_trip(name: str, value: ParamValue, kind: ParamKind) -> ParamValue:
    wire = encode_params({name: value})
    return decode_params(wire, {name: kind})[name]


_TEXT = st.text(min_size=1, max_size=40)
_TERM = st.text(min_size=1, max_size=30)
# A range bound is an ISO date or WDK cannot parse it (WDK-PARAM-006).
_ISO_DATE = st.dates().map(lambda d: d.isoformat())


class TestScalarsRoundTrip:
    @settings(max_examples=200)
    @given(_TEXT)
    def test_string(self, value: str) -> None:
        assert _round_trip("p", StringValue(value=value), "string") == (
            StringValue(value=value)
        )

    @settings(max_examples=200)
    @given(st.integers(min_value=-(10**9), max_value=10**9))
    def test_number(self, value: int) -> None:
        restored = _round_trip("p", NumberValue(value=value), "number")
        assert isinstance(restored, NumberValue)
        assert float(restored.value) == float(value)

    @settings(max_examples=100)
    @given(_TEXT)
    def test_date(self, value: str) -> None:
        assert _round_trip("p", DateValue(value=value), "date") == (
            DateValue(value=value)
        )

    @settings(max_examples=100)
    @given(_TEXT)
    def test_timestamp(self, value: str) -> None:
        assert _round_trip("p", TimestampValue(value=value), "timestamp") == (
            TimestampValue(value=value)
        )


class TestVocabulariesRoundTrip:
    @settings(max_examples=300)
    @given(st.lists(_TERM, max_size=8))
    def test_multi_pick_including_the_empty_selection(self, values: list[str]) -> None:
        """The empty list is the case that produced the ``"[]"`` bug."""
        restored = _round_trip(
            "p", MultiPickValue(values=values), "multi-pick-vocabulary"
        )
        assert restored == MultiPickValue(values=values)

    def test_the_empty_selection_is_not_the_string_bracket_bracket(self) -> None:
        restored = _round_trip("p", MultiPickValue(values=[]), "multi-pick-vocabulary")
        assert restored == MultiPickValue(values=[])
        assert restored != MultiPickValue(values=["[]"])

    @settings(max_examples=200)
    @given(_TERM)
    def test_single_pick(self, value: str) -> None:
        assert _round_trip(
            "p", SinglePickValue(value=value), "single-pick-vocabulary"
        ) == SinglePickValue(value=value)

    @settings(max_examples=200)
    @given(st.lists(st.text(alphabet=",", min_size=1, max_size=3), max_size=4))
    def test_terms_made_of_the_separator(self, values: list[str]) -> None:
        """A comma-joined encoding would lose these silently."""
        restored = _round_trip(
            "p", MultiPickValue(values=values), "multi-pick-vocabulary"
        )
        assert restored == MultiPickValue(values=values)


class TestRangesRoundTrip:
    @settings(max_examples=200)
    @given(
        st.one_of(st.none(), st.integers(min_value=-(10**6), max_value=10**6)),
        st.one_of(st.none(), st.integers(min_value=-(10**6), max_value=10**6)),
    )
    def test_number_range_including_negative_bounds(
        self, low: int | None, high: int | None
    ) -> None:
        assume(low is not None or high is not None)
        assume(low is None or high is None or low <= high)
        restored = _round_trip("p", NumberRangeValue(min=low, max=high), "number-range")
        assert isinstance(restored, NumberRangeValue)
        assert (restored.min is None) == (low is None)
        assert (restored.max is None) == (high is None)
        if low is not None:
            assert float(restored.min or 0) == float(low)
        if high is not None:
            assert float(restored.max or 0) == float(high)

    @settings(max_examples=100)
    @given(st.one_of(st.none(), _ISO_DATE), st.one_of(st.none(), _ISO_DATE))
    def test_date_range(self, low: str | None, high: str | None) -> None:
        assume(low is not None or high is not None)
        restored = _round_trip("p", DateRangeValue(min=low, max=high), "date-range")
        assert restored == DateRangeValue(min=low, max=high)

    def test_a_date_range_whose_bounds_contain_hyphens(self) -> None:
        """ISO dates are full of the character a naive range encoding splits on."""
        value = DateRangeValue(min="2026-01-01", max="2026-12-31")

        assert _round_trip("p", value, "date-range") == value


class TestReferencesRoundTrip:
    @settings(max_examples=100)
    @given(_TERM)
    def test_input_dataset(self, dataset_id: str) -> None:
        assert _round_trip(
            "p", InputDatasetValue(dataset_id=dataset_id), "input-dataset"
        ) == InputDatasetValue(dataset_id=dataset_id)

    @settings(max_examples=100)
    @given(_TERM)
    def test_input_step(self, step_id: str) -> None:
        assert _round_trip(
            "p", InputStepValue(step_id=step_id), "input-step"
        ) == InputStepValue(step_id=step_id)

    def test_an_empty_filter_list(self) -> None:
        value = FilterValue(filters=[])

        assert _round_trip("p", value, "filter") == value
