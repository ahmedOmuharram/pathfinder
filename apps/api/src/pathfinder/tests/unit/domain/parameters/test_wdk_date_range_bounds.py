"""A date-range bound WDK cannot parse is refused here, not on the wire.

``DateRangeParam`` catches the JSON failure and not the date failure, so a
badly formatted bound is a 500 with no diagnosis in it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from pathfinder.domain.parameters.values import DateRangeValue, DateValue


class TestWdkParam006ABoundIsAnIsoDate:
    def test_wdk_param_006_an_iso_bound_is_accepted(self) -> None:
        value = DateRangeValue(min="2026-01-01", max="2026-12-31")

        assert value.to_wire() == '{"min": "2026-01-01", "max": "2026-12-31"}'

    @pytest.mark.parametrize(
        "bound",
        ["01/01/2025", "2025-1-1", "Jan 1 2025", "2025-13-01", "2025-01-32", ""],
    )
    def test_wdk_param_006_a_bound_wdk_cannot_parse_is_refused(
        self, bound: str
    ) -> None:
        with pytest.raises(PydanticValidationError):
            DateRangeValue(min=bound, max="2026-12-31")

    def test_wdk_param_006_the_upper_bound_is_checked_too(self) -> None:
        with pytest.raises(PydanticValidationError):
            DateRangeValue(min="2026-01-01", max="12/31/2026")

    def test_wdk_param_006_an_open_end_stays_open(self) -> None:
        # One end absent is a different question, answered by the parameter's
        # own declared limit.
        assert DateRangeValue(min="2026-01-01").max is None

    def test_wdk_param_006_a_single_date_is_not_constrained_here(self) -> None:
        # DateParam catches its own parse failure, so the refusal is a 422 that
        # names the parameter.
        assert DateValue(value="01/01/2025").to_wire() == "01/01/2025"
