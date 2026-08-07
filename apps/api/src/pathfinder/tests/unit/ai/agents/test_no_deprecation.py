import importlib
import warnings

from pydantic_ai import PydanticAIDeprecationWarning

_AGENT_MODULES = (
    "pathfinder.ai.agents.frame",
    "pathfinder.ai.agents.execution",
    "pathfinder.ai.agents.verification",
    "pathfinder.ai.lead.lead_agent",
)


def test_phase_and_lead_agents_construct_without_pydantic_ai_deprecation() -> None:
    """Reconstructing the phase + lead agents must not trip any pydantic-ai
    deprecation (e.g. the v2 ``history_processors=`` → ``ProcessHistory``
    migration). Reloads under ``simplefilter("always")`` so the construction
    warnings — emitted once at first import — fire again and are captured.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for name in _AGENT_MODULES:
            importlib.reload(importlib.import_module(name))

    offenders = [
        str(w.message)
        for w in caught
        if issubclass(w.category, PydanticAIDeprecationWarning)
    ]
    assert not offenders, offenders
