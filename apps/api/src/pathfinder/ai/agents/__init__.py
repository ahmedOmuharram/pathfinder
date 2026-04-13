"""Agent class definitions and factory."""

from pathfinder.ai.agents.discovery import discovery_agent
from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.agents.scoping import scoping_agent
from pathfinder.ai.agents.verification import verification_agent

# Keys match ``AgentPipeline`` state IDs in ``ai/orchestration/pipeline.py``
# (``scoping``, ``discovery``, ``planning``, ``execution``, ``verification``).
# The pipeline dispatcher looks phase agents up by the current state id.
PHASE_AGENTS = {
    "scoping": scoping_agent,
    "discovery": discovery_agent,
    "planning": planning_agent,
    "execution": execution_agent,
    "verification": verification_agent,
}
