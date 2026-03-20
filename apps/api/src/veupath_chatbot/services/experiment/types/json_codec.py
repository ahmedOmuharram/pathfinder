"""Generic dataclass <-> camelCase JSON conversion.

Replaces the hand-written per-type serialization boilerplate with two
generic functions: ``to_json`` (serialize) and ``from_json`` (deserialize).

Float rounding (default 4 decimal places) can be overridden per-field::

    from dataclasses import field
    total_time_seconds: float = field(default=0.0, metadata={"round": 2})
    p_value: float = field(metadata={"round": None})  # skip rounding
"""

import dataclasses
import functools
import types
from typing import (
    Any,
    Literal,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)


@functools.cache
def _snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


@functools.cache
def _cached_type_hints(cls: type) -> types.MappingProxyType[str, Any]:
    return types.MappingProxyType(get_type_hints(cls))


@functools.cache
def _cached_fields(cls: type) -> tuple[dataclasses.Field[Any], ...]:
    return dataclasses.fields(cls)


# ---------------------------------------------------------------------------
# Serialization: dataclass -> JSON dict
# ---------------------------------------------------------------------------


def to_json(obj: Any, *, _round: int | None = 4) -> Any:
    """Serialize a dataclass (or scalar) to a JSON-compatible value.

    * Dataclass fields are emitted with camelCase keys.
    * Floats are rounded to *_round* decimal places (default 4).
      Override per-field via ``field(metadata={"round": N})``.
    * Lists, tuples, and dicts are handled recursively.
    """
    if obj is None:
        return None
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result: dict[str, Any] = {}
        for f in _cached_fields(type(obj)):
            val = getattr(obj, f.name)
            fr = f.metadata.get("round", _round) if f.metadata else _round
            result[_snake_to_camel(f.name)] = to_json(val, _round=fr)
        return result
    if isinstance(obj, float):
        return round(obj, _round) if _round is not None else obj
    if isinstance(obj, (list, tuple)):
        return [to_json(item, _round=_round) for item in obj]
    if isinstance(obj, dict):
        return {str(k): to_json(v, _round=_round) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Deserialization: JSON dict -> dataclass
# ---------------------------------------------------------------------------


def from_json[T](data: dict[str, Any], cls: type[T]) -> T:
    """Construct a *cls* dataclass from a camelCase JSON dict.

    Nested dataclasses, lists, dicts, and tuples are coerced using
    type-hint introspection.  Missing keys fall back to field defaults.
    """
    # Bind to plain ``type`` so the cached helpers see a Hashable arg.
    concrete: type = cls
    hints = _cached_type_hints(concrete)
    kwargs: dict[str, Any] = {}
    for f in _cached_fields(concrete):
        camel = _snake_to_camel(f.name)
        raw = data.get(camel, dataclasses.MISSING)
        if raw is dataclasses.MISSING:
            # Let the dataclass use its own default (or error if required).
            continue
        hint = hints.get(f.name)
        kwargs[f.name] = _coerce(raw, hint) if hint else raw
    return cls(**kwargs)


def _coerce(value: Any, hint: Any) -> Any:
    """Coerce a JSON value to match *hint*."""
    if value is None:
        return None

    # Unwrap Python 3.12+ ``type X = ...`` aliases.
    if isinstance(hint, TypeAliasType):
        hint = hint.__value__

    # Nested dataclass
    if dataclasses.is_dataclass(hint) and isinstance(hint, type):
        return from_json(value, hint) if isinstance(value, dict) else value

    origin = get_origin(hint)
    args = get_args(hint)

    # Handle Union and Optional types
    if origin is Union or origin is types.UnionType:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _coerce(value, non_none[0])
        return value

    # Literal — pass through
    if origin is Literal:
        return value

    # Handle generic list types
    if origin is list and isinstance(value, list):
        if args:
            return [_coerce(item, args[0]) for item in value]
        return value

    # Handle generic tuple types
    if origin is tuple and isinstance(value, (list, tuple)):
        if args:
            return tuple(
                _coerce(v, args[min(i, len(args) - 1)]) for i, v in enumerate(value)
            )
        return tuple(value)

    # Handle generic dict types
    if origin is dict and isinstance(value, dict):
        if args and len(args) == 2:
            kt, vt = args
            return {
                (int(k) if kt is int else k): _coerce(v, vt) for k, v in value.items()
            }
        return value

    return value
