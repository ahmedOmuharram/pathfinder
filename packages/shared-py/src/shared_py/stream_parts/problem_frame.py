"""Typed payload for problem_frame data-part.

Mirrors the internal ``pathfinder.ai.graph.state.ProblemFrame`` field-for-field
so the UI can render every piece of context the scoping agent captured, not
just a summary blurb. Sent as the payload of the ``data-problem-frame``
``DataChunk`` when the scoping agent calls ``set_problem_frame``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from shared_py.pydantic_base import CamelModel


class ClarificationQuestion(CamelModel):
    question: str
    context: str = ""
    field: str | None = None
    priority: Literal["blocking", "optional"] = "blocking"
    options: list[str] = Field(default_factory=list)


class ResearchNote(CamelModel):
    source: str
    finding: str
    url: str | None = None
    citation_id: str | None = None


class ProblemFrame(CamelModel):
    site_id: str
    user_goal: str
    interpreted_goal: str
    organism_scope: str | None = None
    record_type: str | None = None
    biological_entities: list[str] = Field(default_factory=list)
    inclusion_criteria: list[str] = Field(default_factory=list)
    exclusion_criteria: list[str] = Field(default_factory=list)
    likely_data_sources: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    blocking_questions: list[ClarificationQuestion] = Field(default_factory=list)
    optional_questions: list[ClarificationQuestion] = Field(default_factory=list)
    research_notes: list[ResearchNote] = Field(default_factory=list)
    ready_for_wdk_discovery: bool = False
    confidence: float = 0.0
