"""Agent tool registration mixin (aggregator).

Composes category-specific mixins into a single ``AgentToolRegistryMixin``
that provides all @ai_function methods for the agent.
"""

from veupath_chatbot.ai.tools.catalog_registry import CatalogToolsMixin
from veupath_chatbot.ai.tools.research_registry import ResearchToolsMixin
from veupath_chatbot.ai.tools.strategy_registry import StrategyToolsMixin


class AgentToolRegistryMixin(
    CatalogToolsMixin,
    StrategyToolsMixin,
    ResearchToolsMixin,
):
    """Mixin for agent tool registration.

    Inherits ``web_search`` and ``literature_search`` from
    :class:`ResearchToolsMixin`.

    Inherits catalog lookup tools from :class:`CatalogToolsMixin`.

    Inherits strategy, execution, result, and conversation tools from
    :class:`StrategyToolsMixin` (auto-delegated to underlying tool instances).

    Classes using this mixin must provide these attributes:
    - site_id: str
    - catalog_tools: CatalogTools
    - catalog_rag_tools: CatalogRagTools
    - example_plans_rag_tools: ExamplePlansRagTools
    - strategy_tools: StrategyTools
    - execution_tools: ExecutionTools
    - result_tools: ResultTools
    - conversation_tools: ConversationTools
    - web_search_service: WebSearchService
    - literature_search_service: LiteratureSearchService
    """
