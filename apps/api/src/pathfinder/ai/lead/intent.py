from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from pathfinder.domain.strategy.constraints import Constraint
from pathfinder.platform.pydantic_base import CamelModel


class IntentClassification(StrEnum):
    NEW_STRATEGY = "new_strategy"
    EXTEND_STRATEGY = "extend_strategy"
    EDIT_STRATEGY = "edit_strategy"
    FOLLOW_UP_QUESTION = "follow_up_question"
    CLARIFICATION_RESPONSE = "clarification_response"
    SLOT_ANSWER = "slot_answer"
    APPROVAL = "approval"
    DENIAL = "denial"
    OFF_TOPIC = "off_topic"


class UserIntent(CamelModel):
    """The Lead's typed parsing of the latest user message.

    Distinct from ``ProblemFrame``: ``UserIntent`` is per-message and
    re-derived each turn; ``ProblemFrame`` is the durable scoping artifact.
    The Lead writes this via the ``classify_user_intent`` tool as its
    first action on a new user message; the Ledger then derives downstream
    booleans (e.g. ``intent_satisfied``) from typed fields here.
    """

    raw_text: str
    classification: IntentClassification
    inferred_goal: str = Field(max_length=500)
    is_differential: bool = False
    differential_sides: list[str] = Field(
        default_factory=list,
        max_length=2,
        description=(
            "Two-item list of comparison conditions when "
            "``is_differential`` is True (e.g. ``['asexual', 'gametocyte']``). "
            "Empty otherwise."
        ),
    )
    referenced_step_ids: list[str] = Field(default_factory=list)
    referenced_strategy_ids: list[int] = Field(default_factory=list)
    explicit_constraints: list[Constraint] = Field(
        default_factory=list,
        description=(
            "Typed constraints the user STATED in this message (data_type, "
            "statistical_threshold, fold_change, comparator, organism, "
            "record_type). Captured fresh each turn from the literal message — "
            "these are user-explicit by construction and override scoping's "
            "provisional assumptions for the same dimension."
        ),
    )
    last_classified_at_turn: str | None = None
