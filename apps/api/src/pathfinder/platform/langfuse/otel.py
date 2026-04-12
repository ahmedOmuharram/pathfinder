"""Helpers for mapping OpenTelemetry span attributes into Langfuse fields."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from opentelemetry.trace import Span


@dataclass(frozen=True)
class LangfuseTraceContext:
    """Stable trace context propagated to every span in a turn."""

    user_id: str | None = None
    session_id: str | None = None
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] | None = None
    release: str | None = None
    environment: str | None = None


@dataclass(frozen=True)
class LangfuseTraceAttributes:
    """Trace-specific Langfuse fields owned by the root span."""

    name: str | None = None
    input_value: Any | None = None
    output_value: Any | None = None
    as_root: bool = False


def _serialize_value(value: Any) -> str | None:
    """Convert metadata values into Langfuse-safe strings."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def _set_metadata_prefix(
    span: Span,
    *,
    prefix: str,
    metadata: Mapping[str, Any] | None,
) -> None:
    if metadata is None:
        return
    for key, value in metadata.items():
        serialized = _serialize_value(value)
        if serialized is None:
            continue
        span.set_attribute(f"{prefix}{key}", serialized)


def _normalize_tags(tags: Iterable[str] | None) -> tuple[str, ...]:
    if tags is None:
        return ()
    return tuple(tags)


def propagate_langfuse_trace_context(
    span: Span,
    trace_ctx: LangfuseTraceContext,
) -> None:
    """Propagate stable trace fields onto any span in the trace tree."""
    if trace_ctx.user_id is not None:
        span.set_attribute("user.id", trace_ctx.user_id)
        span.set_attribute("langfuse.user.id", trace_ctx.user_id)
    if trace_ctx.session_id is not None:
        span.set_attribute("session.id", trace_ctx.session_id)
        span.set_attribute("langfuse.session.id", trace_ctx.session_id)
    if trace_ctx.tags:
        span.set_attribute("langfuse.trace.tags", list(trace_ctx.tags))
    if trace_ctx.release is not None:
        span.set_attribute("langfuse.release", trace_ctx.release)
    if trace_ctx.environment is not None:
        span.set_attribute("langfuse.environment", trace_ctx.environment)
    _set_metadata_prefix(
        span,
        prefix="langfuse.trace.metadata.",
        metadata=trace_ctx.metadata,
    )


def set_langfuse_trace_attributes(
    span: Span,
    trace_attrs: LangfuseTraceAttributes,
    *,
    trace_ctx: LangfuseTraceContext | None = None,
) -> None:
    """Set trace-level Langfuse attributes on a span."""
    if trace_attrs.as_root:
        root_flag = True
        span.set_attribute("langfuse.internal.as_root", root_flag)
        span.set_attribute("langfuse.observation.type", "span")
    if trace_attrs.name is not None:
        span.set_attribute("langfuse.trace.name", trace_attrs.name)
    if trace_ctx is not None:
        propagate_langfuse_trace_context(span, trace_ctx)
    if trace_attrs.input_value is not None:
        serialized = _serialize_value(trace_attrs.input_value)
        if serialized is not None:
            span.set_attribute("langfuse.trace.input", serialized)
            span.set_attribute("langfuse.observation.input", serialized)
    if trace_attrs.output_value is not None:
        serialized = _serialize_value(trace_attrs.output_value)
        if serialized is not None:
            span.set_attribute("langfuse.trace.output", serialized)
            span.set_attribute("langfuse.observation.output", serialized)


def set_langfuse_observation_attributes(
    span: Span,
    *,
    observation_type: str | None = None,
    input_value: Any | None = None,
    output_value: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Set observation-level Langfuse attributes on a span."""
    if observation_type is not None:
        span.set_attribute("langfuse.observation.type", observation_type)
    if input_value is not None:
        serialized = _serialize_value(input_value)
        if serialized is not None:
            span.set_attribute("langfuse.observation.input", serialized)
    if output_value is not None:
        serialized = _serialize_value(output_value)
        if serialized is not None:
            span.set_attribute("langfuse.observation.output", serialized)
    _set_metadata_prefix(
        span,
        prefix="langfuse.observation.metadata.",
        metadata=metadata,
    )
