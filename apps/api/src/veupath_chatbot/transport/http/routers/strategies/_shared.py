"""Shared helpers for strategies routers."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.schemas import StepResponse


def build_step_response(step: JSONObject) -> StepResponse:
    # Pydantic models accept dict[str, Any] for model_validate
    return StepResponse.model_validate(cast(dict[str, object], step))
