"""The agent that reads a controlled vocabulary and picks a value.

It answers with a value it was shown, or with nothing. Nothing becomes a
question for the user, never a WDK default.
"""

from __future__ import annotations

from functools import cache

from pydantic import Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel

logger = get_logger(__name__)

# The ceiling bounds the cost of one parameter, whatever the vocabulary size.
MAX_PROMPT_TOKENS = 100_000
# A low estimate of characters per token. A high count drops candidates, a
# low count raises the cost.
_CHARS_PER_TOKEN = 3

_INSTRUCTIONS = """\
You map one phrase from a scientist's request onto one value from a controlled \
vocabulary.

You are given the criterion text and a list of candidate values. Return the \
candidate the criterion calls for.

Rules:
- Return ONLY the value, exactly as printed before any parenthesis. For a \
candidate rendered "- DeRisi 3D7 Smoothed  (iRBC 3D7)", answer \
"DeRisi 3D7 Smoothed". Never invent one.
- If the parameter accepts MANY values and the criterion names a range or a \
group, return every candidate it covers. "20-32 hours" over hourly candidates \
is thirteen values, not one -- returning one searches a narrower question than \
the one asked. If it accepts ONE value, return exactly one.
- If the criterion does not determine a value, return an empty list. That is \
correct and useful: it becomes a question for the scientist. A plausible-looking \
guess is not, because it becomes a silently wrong result they cannot see.
- Read the criterion for what it asks, not for surface similarity. "non-syntenic" \
means the syntenic flag is off. "top 10 percent" is a bound, not a label.
"""


_FREE_VALUE_INSTRUCTIONS = """\
You read one value for one search parameter out of a scientist's request.

You are given the criterion text, the parameter's name, its type, and its help \
text. Return the value the request states for THAT parameter.

Rules:
- Return the value only: "2", not "2 peptides"; "kinase", not "the term kinase".
- The criterion may state several numbers. Use the parameter's name and help \
text to decide which one belongs to this parameter, and return null if you \
cannot tell.
- If the request does not state a value for this parameter, return null. Null is \
correct: it becomes a question. Never supply a plausible-looking value the \
request does not contain -- the parameter's own default is a placeholder, and a \
guess here silently changes what was searched.
"""


class FreeValue(CamelModel):
    """A value read out of the request for a param with no vocabulary."""

    value: str | None = Field(
        default=None,
        description="The value the request states, or null if it states none.",
    )
    reason: str = Field(default="", description="One short clause. For traces.")


class VocabDecision(CamelModel):
    """The candidate values the resolver chose, possibly none.

    A single-pick parameter gets a list of one. The caller refuses a longer list.
    """

    values: list[str] = Field(
        default_factory=list,
        description=(
            "The candidate values the criterion calls for, copied exactly. "
            "Empty when the criterion does not determine any."
        ),
    )
    reason: str = Field(default="", description="One short clause. For traces.")


def _fits(candidates: list[VocabOption], budget_chars: int) -> list[VocabOption]:
    kept: list[VocabOption] = []
    used = 0
    for option in candidates:
        line = len(option.value) + len(option.display or "") + 4
        if used + line > budget_chars:
            break
        kept.append(option)
        used += line
    return kept


def match_candidate(answer: str, candidates: list[VocabOption]) -> str | None:
    """Resolves the answer to the value of one candidate, or to None.

    An answer can hold any form that this module prints for a candidate.
    An answer that matches no candidate is refused.
    """
    cleaned = answer.strip().removeprefix("-").strip()
    for option in candidates:
        if cleaned == option.value:
            return option.value
    for option in candidates:
        if cleaned in (_line(option), option.display):
            return option.value
    for option in candidates:
        if cleaned.startswith(f"{option.value} ("):
            return option.value
    return None


def _line(option: VocabOption) -> str:
    if not option.display or option.display == option.value:
        return option.value
    return f"{option.value}  ({option.display})"


def _render(candidates: list[VocabOption]) -> str:
    return "\n".join(f"- {_line(o)}" for o in candidates)


RESOLVER_MODEL = "openai:gpt-5.6-luna"


@cache
def resolver_agent() -> Agent[None, VocabDecision]:
    """Builds the agent on first use, not at import.

    Agent construction opens a provider client, so an import must not do it.
    """
    return Agent(
        RESOLVER_MODEL,
        output_type=VocabDecision,
        instructions=_INSTRUCTIONS,
        name="vocab_resolver",
    )


@cache
def free_value_agent() -> Agent[None, FreeValue]:
    """Builds the agent on first use, not at import."""
    return Agent(
        RESOLVER_MODEL,
        output_type=FreeValue,
        instructions=_FREE_VALUE_INSTRUCTIONS,
        name="free_value_resolver",
    )


async def resolve_free_value(
    text: str,
    *,
    param_name: str,
    param_type: str,
    help_text: str,
) -> str | None:
    """Reads the value of a parameter that has no vocabulary from the criterion.

    There is no candidate list here, so WDK validation is the only check.
    The result must never hold a value that the request does not state.
    """
    prompt = (
        f"Criterion:\n{text}\n\n"
        f"Parameter: {param_name}\nType: {param_type}\nHelp: {help_text}"
    )
    try:
        result = await free_value_agent().run(
            prompt,
            usage_limits=UsageLimits(request_limit=2, tool_calls_limit=0),
        )
    except UsageLimitExceeded as exc:
        logger.warning("free value resolver hit its ceiling", error=str(exc))
        return None
    value = (result.output.value or "").strip()
    return value or None


async def resolve_vocabulary_value(
    text: str,
    *,
    param_name: str,
    param_help: str,
    accepts_many: bool,
    candidates: list[VocabOption],
) -> str | list[str] | None:
    """Picks the candidates that the criterion calls for, or returns None.

    The parameter name and help identify which vocabulary the list belongs to.
    This function does not raise, because a failure must become a question.
    """
    if not candidates:
        return None
    affordable = _fits(candidates, MAX_PROMPT_TOKENS * _CHARS_PER_TOKEN)
    if len(affordable) < len(candidates):
        logger.warning(
            "vocabulary truncated to fit the resolver budget",
            offered=len(candidates),
            sent=len(affordable),
        )
    if not affordable:
        return None

    arity = (
        "This parameter accepts MANY values."
        if accepts_many
        else "This parameter accepts exactly ONE value."
    )
    prompt = (
        f"Criterion:\n{text}\n\n"
        f"Parameter: {param_name}\nHelp: {param_help}\n{arity}\n\n"
        f"Candidates:\n{_render(affordable)}"
    )
    try:
        result = await resolver_agent().run(
            prompt,
            usage_limits=UsageLimits(request_limit=2, tool_calls_limit=0),
        )
    except UsageLimitExceeded as exc:
        logger.warning("vocab resolver hit its ceiling", error=str(exc))
        return None
    matched: list[str] = []
    for answer in result.output.values:
        chosen = match_candidate(answer, affordable)
        if chosen is None:
            # Refuse the whole answer: keeping the elements that do match would
            # search a narrower question than the one asked, invisibly.
            logger.warning(
                "vocab resolver answered outside its candidates", value=answer
            )
            return None
        matched.append(chosen)
    if not matched:
        return None
    return matched if accepts_many else matched[0]
