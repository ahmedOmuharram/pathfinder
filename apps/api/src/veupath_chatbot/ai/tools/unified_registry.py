"""Unified tool registration mixin — executor + planning tools.

Combines the executor's graph-building / execution tools with
the planner's research, validation, and optimization tools so a
single agent can decide which capabilities to use per turn.

**Not included** from the planner:

* ``DelegationToolsMixin`` – the unified agent already has
  ``delegate_strategy_subtasks``, so plan-session delegation
  drafting/requesting is not applicable.
* ``SiteCatalogToolsMixin`` – duplicate of executor catalog tools.
* ``list_saved_planning_artifacts`` / ``get_saved_planning_artifact``
  – removed from ArtifactToolsMixin. Artifacts are embedded in
  strategy messages.
"""

from veupath_chatbot.ai.tools.export_tools import ExportToolsMixin
from veupath_chatbot.ai.tools.planner.artifact_tools import ArtifactToolsMixin
from veupath_chatbot.ai.tools.planner.experiment_tools import ExperimentToolsMixin
from veupath_chatbot.ai.tools.planner.gene_tools import GeneToolsMixin
from veupath_chatbot.ai.tools.planner.optimization_tools import OptimizationToolsMixin
from veupath_chatbot.ai.tools.planner.workbench_tools import WorkbenchToolsMixin
from veupath_chatbot.ai.tools.registry import AgentToolRegistryMixin


class UnifiedToolRegistryMixin(
    ExportToolsMixin,
    GeneToolsMixin,
    ExperimentToolsMixin,
    OptimizationToolsMixin,
    WorkbenchToolsMixin,
    ArtifactToolsMixin,
    AgentToolRegistryMixin,
):
    """Combined tool registry for the unified agent.

    MRO places planner tool mixins first so they can override any
    shared method names if needed (they don't currently), and
    ``AgentToolRegistryMixin`` last so its ``ResearchToolsMixin``
    (``web_search``, ``literature_search``) is available to all.

    Classes using this mixin must provide the same attributes as
    ``AgentToolRegistryMixin`` plus ``site_id: str``.

    The ``_emit_event`` method (required by ``OptimizationToolsMixin``)
    is provided by ``PathfinderAgent`` which pushes events onto its
    streaming ``event_queue``.
    """

    pass
