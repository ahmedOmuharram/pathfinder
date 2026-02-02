"""Utilities for strategy AST traversal."""

from __future__ import annotations

from veupath_chatbot.domain.strategy.ast import CombineStep, SearchStep, TransformStep


def infer_record_type_from_step(step: SearchStep | CombineStep | TransformStep) -> str | None:
    if isinstance(step, SearchStep):
        return step.record_type
    if isinstance(step, TransformStep):
        return infer_record_type_from_step(step.input)
    if isinstance(step, CombineStep):
        return infer_record_type_from_step(step.left) or infer_record_type_from_step(step.right)
    return None

