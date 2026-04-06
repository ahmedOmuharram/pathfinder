"""Request classification for the agent pipeline.

Tier 1 (rule-based) handles ~65-70% of requests instantly and for free.
Tier 2 (cheapest available LLM) handles the remaining ambiguous cases.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel
from pydantic_ai import Agent

from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)


class Intent(StrEnum):
    """User request intent categories."""

    NEW_STRATEGY = "new_strategy"
    EXTEND_STRATEGY = "extend_strategy"
    EDIT_STRATEGY = "edit_strategy"
    QUESTION = "question"


class ClassificationResult(BaseModel):
    """Result of request classification."""

    intent: Intent
    confidence: float
    reasoning: str


# --- Patterns ---

_INTERROGATIVE_STARTS = re.compile(
    r"^\s*(what|how|why|when|where|which|who|does|is|are|can|could|"
    r"do |tell me|explain|describe|show me|help me understand)\b",
    re.IGNORECASE,
)

_CREATION_KEYWORDS = re.compile(
    r"\b(find|search for|look for|build|create|construct|make|"
    r"identify|discover|get me|give me|show me.*genes|"
    r"i want|i need|i\'m looking for|"
    r"genes? (?:that|which|with|in|expressed|involved)|"
    r"strategy (?:for|to|that))\b",
    re.IGNORECASE,
)

_EXTENSION_KEYWORDS = re.compile(
    r"\b(also|additionally|add|include|intersect with|union with|"
    r"combine with|and also|plus|on top of that|"
    r"extend|supplement|augment|furthermore|"
    r"narrow down|filter by|restrict to)\b",
    re.IGNORECASE,
)

_EDIT_KEYWORDS = re.compile(
    r"\b(change|modify|update|set|switch|replace|rename|"
    r"fix|correct|adjust|alter|"
    r"the (?:organism|parameter|filter|operator|name)|"
    r"step.{0,20}(?:parameter|organism|filter|name))\b",
    re.IGNORECASE,
)

_STEP_REFERENCE = re.compile(
    r"\b(?:step[_ ]?\d+|step_\w+)\b",
    re.IGNORECASE,
)

_APPROVAL_PATTERNS = re.compile(
    r"^\s*(?:yes|yeah|yep|ok|okay|approve|approved|looks good|"
    r"go ahead|proceed|do it|execute|build it|run it|lgtm)\s*[.!]?\s*$",
    re.IGNORECASE,
)

_REVISION_PATTERNS = re.compile(
    r"^\s*(?:revise|change|modify|no,? |wait,? |actually,? |instead)",
    re.IGNORECASE,
)

_SHORT_MESSAGE_WORD_LIMIT = 5


def classify_request(
    message: str,
    *,
    graph: StrategyGraph | None = None,
    has_pending_plan: bool = False,
) -> ClassificationResult | None:
    """Classify a user message using rule-based heuristics.

    Returns a ``ClassificationResult`` if confident, or ``None`` if the
    message is ambiguous and should fall through to the LLM tier.

    Parameters
    ----------
    message:
        The raw user message text.
    graph:
        The current strategy graph, if one exists.
    has_pending_plan:
        Whether a plan is awaiting user approval.
    """
    text = message.strip()
    has_strategy = graph is not None and bool(graph.steps)

    # --- Plan approval/revision (highest priority) ---
    if has_pending_plan:
        if _APPROVAL_PATTERNS.match(text):
            return ClassificationResult(
                intent=Intent.EDIT_STRATEGY,
                confidence=0.95,
                reasoning="Approval pattern detected with pending plan",
            )
        if _REVISION_PATTERNS.match(text):
            return ClassificationResult(
                intent=Intent.EDIT_STRATEGY,
                confidence=0.90,
                reasoning="Revision pattern detected with pending plan",
            )

    # --- Pure questions (high confidence) ---
    if _INTERROGATIVE_STARTS.match(text) and not _CREATION_KEYWORDS.search(text):
        return ClassificationResult(
            intent=Intent.QUESTION,
            confidence=0.85,
            reasoning="Interrogative pattern without creation keywords",
        )

    # --- Edit: step references + existing strategy ---
    if has_strategy and _STEP_REFERENCE.search(text) and _EDIT_KEYWORDS.search(text):
        return ClassificationResult(
            intent=Intent.EDIT_STRATEGY,
            confidence=0.85,
            reasoning="Step reference + edit keywords + existing strategy",
        )

    # --- Edit: parameter/operator changes on existing strategy ---
    if has_strategy and _EDIT_KEYWORDS.search(text) and not _CREATION_KEYWORDS.search(text):
        return ClassificationResult(
            intent=Intent.EDIT_STRATEGY,
            confidence=0.75,
            reasoning="Edit keywords + existing strategy, no creation keywords",
        )

    # --- Extension: extend keywords + existing strategy ---
    if has_strategy and _EXTENSION_KEYWORDS.search(text):
        return ClassificationResult(
            intent=Intent.EXTEND_STRATEGY,
            confidence=0.80,
            reasoning="Extension keywords + existing strategy",
        )

    # --- New: creation keywords + no strategy ---
    if not has_strategy and _CREATION_KEYWORDS.search(text):
        return ClassificationResult(
            intent=Intent.NEW_STRATEGY,
            confidence=0.85,
            reasoning="Creation keywords, no existing strategy",
        )

    # --- New: creation keywords + existing strategy (might be extend) ---
    if has_strategy and _CREATION_KEYWORDS.search(text):
        # Ambiguous — could be EXTEND or NEW. Fall through to LLM.
        return None

    # --- Fallback question for short ambiguous messages ---
    if len(text.split()) <= _SHORT_MESSAGE_WORD_LIMIT and not _CREATION_KEYWORDS.search(text):
        return ClassificationResult(
            intent=Intent.QUESTION,
            confidence=0.60,
            reasoning="Short message without creation keywords",
        )

    # --- Ambiguous — LLM tier needed ---
    return None


# ---------------------------------------------------------------------------
# Tier 2: LLM-based classification for ambiguous requests
# ---------------------------------------------------------------------------

_LLM_CLASSIFIER_PROMPT = """\
Classify the user's intent for a bioinformatics strategy builder.

User message: {message}
Has existing strategy: {has_strategy}
Has pending plan: {has_pending_plan}

Return exactly one intent:
- NEW_STRATEGY: User wants to create a new search strategy from scratch.
- EXTEND_STRATEGY: User wants to add steps to an existing strategy.
- EDIT_STRATEGY: User wants to modify parameters or steps of the existing strategy.
- QUESTION: User is asking a question, not requesting strategy changes.
"""

_classifier_agent: Agent[None, ClassificationResult] = Agent(
    "anthropic:claude-sonnet-4-5",
    output_type=ClassificationResult,
    instructions="Classify user intent. Be concise in reasoning.",
    defer_model_check=True,
)


async def classify_request_llm(
    message: str,
    *,
    model_id: str,
    graph: StrategyGraph | None = None,
    has_pending_plan: bool = False,
) -> ClassificationResult:
    """Tier 2: Use the configured LLM to classify ambiguous requests.

    Called when the rule-based tier returns None. Uses the user's
    configured model (resolved by the orchestrator).
    """
    prompt = _LLM_CLASSIFIER_PROMPT.format(
        message=message,
        has_strategy=graph is not None and bool(graph.steps),
        has_pending_plan=has_pending_plan,
    )
    try:
        with _classifier_agent.override(model=model_id):
            result = await _classifier_agent.run(prompt)
    except Exception:
        logger.exception("LLM classifier failed, defaulting to NEW_STRATEGY")
        return ClassificationResult(
            intent=Intent.NEW_STRATEGY,
            confidence=0.5,
            reasoning="LLM classification failed, defaulting to full pipeline",
        )
    else:
        return result.output
