"""#2: ``create_plan`` must coerce a number value to a WDK string param.

WDK models numeric params (e.g. ``fold_change``) as ``StringParam`` with
``isNumber=True``. The planning agent naturally sends a ``number`` value; the
old ``_build_param`` rejected it (``value.type 'number' != param_type
'string'``), looping the agent. WDK is stringly-typed, so the value is coerced
to its string form instead of rejected.
"""

from __future__ import annotations

import pytest

from pathfinder.ai.tools.standalone._plan_models import _build_param
from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import (
    MultiPickValue,
    NumberValue,
)


def test_build_param_coerces_number_to_string_for_wdk_string_param() -> None:
    spec = ParamSpecNormalized(
        name="fold_change",
        param_type="string",
        is_number=True,
    )
    planned = _build_param("fold_change", NumberValue(value=2.0), spec)
    assert planned.param_type == "string"
    assert planned.value is not None
    assert planned.value.type == "string"
    assert planned.value.value == "2"


def test_build_param_rejects_structurally_incompatible_value() -> None:
    spec = ParamSpecNormalized(name="fold_change", param_type="string")
    with pytest.raises(ValueError, match="fold_change"):
        _build_param("fold_change", MultiPickValue(values=["a", "b"]), spec)
