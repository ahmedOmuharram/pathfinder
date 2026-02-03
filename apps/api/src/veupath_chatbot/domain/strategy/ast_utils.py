"""Utilities for strategy AST traversal."""

from __future__ import annotations

from veupath_chatbot.domain.strategy.ast import PlanStepNode


def infer_kind_from_step(step: PlanStepNode) -> str:
    """Infer kind from step structure (search/transform/combine)."""
    return step.infer_kind()

