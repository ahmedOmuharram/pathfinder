"""Agent tool registration mixin (aggregator).

Composes category-specific mixins into a single ``AgentToolRegistryMixin``
that provides all @ai_function methods for the agent.

Tool discovery: ``StrategyToolsMixin`` uses ``__dir__``/``__getattr__`` to
delegate @ai_function methods from tool instances (including ``catalog_tools``,
``strategy_tools``, ``execution_tools``, etc.) to the agent class so kani
discovers them.
"""

from veupath_chatbot.ai.tools.research_registry import ResearchToolsMixin
from veupath_chatbot.ai.tools.strategy_registry import StrategyToolsMixin


class AgentToolRegistryMixin(
    StrategyToolsMixin,
    ResearchToolsMixin,
):
    """Mixin for agent tool registration.

    Tool instances are discovered via ``_TOOL_ATTRS`` in
    ``StrategyToolsMixin.__dir__``/``__getattr__``.

    Classes using this mixin must provide these attributes:
    - catalog_tools: CatalogTools
    - strategy_tools: StrategyTools
    - execution_tools: ExecutionTools
    - result_tools: ResultTools
    - conversation_tools: ConversationTools
    - web_search_service: WebSearchService
    - literature_search_service: LiteratureSearchService
    """
