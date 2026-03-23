"""Workbench AI chat agent.

Conversational agent for experiment result exploration. Composes
research, catalog, analysis, refinement, gene, and workbench tool mixins.
"""

from uuid import UUID

from kani import ChatMessage, Kani
from kani.engines.base import BaseEngine

from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.planner.gene_tools import GeneToolsMixin
from veupath_chatbot.ai.tools.planner.workbench_tools import WorkbenchToolsMixin
from veupath_chatbot.ai.tools.research_registry import ResearchToolsMixin
from veupath_chatbot.ai.tools.strategy_registry import StrategyToolsMixin
from veupath_chatbot.ai.tools.workbench_read_tools import WorkbenchReadToolsMixin
from veupath_chatbot.services.experiment.ai_analysis_tools import _AnalysisToolsMixin
from veupath_chatbot.services.experiment.ai_refinement_tools import RefinementToolsMixin
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import Experiment
from veupath_chatbot.services.research import LiteratureSearchService, WebSearchService


class WorkbenchAgent(
    WorkbenchReadToolsMixin,
    RefinementToolsMixin,
    _AnalysisToolsMixin,
    GeneToolsMixin,
    WorkbenchToolsMixin,
    StrategyToolsMixin,
    ResearchToolsMixin,
    Kani,
):
    """Conversational AI agent for the workbench.

    CatalogTools methods are discovered via kani's dir() traversal
    of self.catalog_tools (an attribute, not a mixin).
    """

    def __init__(
        self,
        engine: BaseEngine,
        site_id: str,
        experiment_id: str,
        user_id: UUID | None = None,
        system_prompt: str = "",
        chat_history: list[ChatMessage] | None = None,
    ) -> None:
        self.site_id = site_id
        self.experiment_id = experiment_id
        self.user_id = user_id

        # Research tools
        self.web_search_service = WebSearchService()
        self.literature_search_service = LiteratureSearchService()

        # Catalog tools (discovered by kani via dir(self))
        self.catalog_tools = CatalogTools(site_id)

        super().__init__(
            engine=engine,
            system_prompt=system_prompt,
            chat_history=chat_history or [],
        )

    async def _get_experiment(self) -> Experiment | None:
        store = get_experiment_store()
        return await store.get(self.experiment_id)
