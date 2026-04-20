"""Pure value-shape utilities for parameter handling."""

from pydantic import JsonValue

from pathfinder.platform.errors import ValidationError


def ensure_list(value: JsonValue, name: str) -> list[JsonValue]:
    """Lift a JsonValue into a list.

    Scalars become single-element lists; lists/tuples/sets become lists;
    ``None`` becomes an empty list; dicts raise a ``ValidationError`` since
    no parameter type accepts a dict where a list is expected.
    """
    if value is None:
        return []
    if isinstance(value, dict):
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{name}' does not accept dictionaries.",
            errors=[{"param": name, "value": value}],
        )
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if v is not None]
    return [value]
