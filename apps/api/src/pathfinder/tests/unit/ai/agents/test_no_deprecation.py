import warnings

from pydantic_ai import PydanticAIDeprecationWarning

from pathfinder.ai.agents.execution import build_execution_agent
from pathfinder.ai.agents.frame import build_frame_agent
from pathfinder.ai.agents.verification import build_verification_agent
from pathfinder.ai.lead.lead_agent import build_lead_agent

_BUILDERS = (
    build_frame_agent,
    build_execution_agent,
    build_verification_agent,
    build_lead_agent,
)


def test_phase_and_lead_agents_construct_without_pydantic_ai_deprecation() -> None:
    """Building the phase and Lead agents must not trip any pydantic-ai
    deprecation (e.g. the v2 ``history_processors=`` -> ``ProcessHistory``
    migration). ``simplefilter("always")`` keeps a warning that fires on an
    earlier build from being swallowed here.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for build in _BUILDERS:
            build()

    offenders = [
        str(w.message)
        for w in caught
        if issubclass(w.category, PydanticAIDeprecationWarning)
    ]
    assert not offenders, offenders
