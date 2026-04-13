"""Typed payload for problem_frame data-part."""

from __future__ import annotations

from shared_py.pydantic_base import CamelModel


class ProblemFrame(CamelModel):
    intent_summary: str
    entities: list[str]
    site_id: str
