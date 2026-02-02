"""Shared helpers for strategies routers."""

from __future__ import annotations

from typing import Any

from veupath_chatbot.transport.http.schemas import StepResponse


def build_step_response(step: dict[str, Any]) -> StepResponse:
    return StepResponse(**step)

