"""Strategy, execution, result, and conversation tool delegation.

Instead of manually re-declaring every @ai_function as a pass-through,
this mixin delegates attribute lookups to the underlying tool instances.
Kani discovers tools via ``dir(self)`` + ``getattr(self, name)``; by
overriding both, all @ai_function methods on the composed tool objects
are surfaced to the agent framework automatically.
"""

import contextlib
import inspect
from typing import cast

from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.ai.tools.execution_tools import ExecutionTools
from veupath_chatbot.ai.tools.result_tools import ResultTools
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools

# Attribute names for the tool instances that hold @ai_function methods.
_TOOL_ATTRS = (
    "strategy_tools",
    "execution_tools",
    "result_tools",
    "conversation_tools",
)


class StrategyToolsMixin:
    """Mixin providing strategy, execution, result, and conversation @ai_function methods.

    Classes using this mixin must set these attributes before Kani.__init__
    runs (which is where tool discovery happens):

    - strategy_tools: StrategyTools
    - execution_tools: ExecutionTools
    - result_tools: ResultTools
    - conversation_tools: ConversationTools
    """

    strategy_tools: StrategyTools = cast("StrategyTools", cast("object", None))
    execution_tools: ExecutionTools = cast("ExecutionTools", cast("object", None))
    result_tools: ResultTools = cast("ResultTools", cast("object", None))
    conversation_tools: ConversationTools = cast(
        "ConversationTools", cast("object", None)
    )

    def _tool_instances(self) -> list[object]:
        """Return the concrete tool instances to delegate to."""
        instances: list[object] = []
        for attr in _TOOL_ATTRS:
            with contextlib.suppress(AttributeError):
                instances.append(object.__getattribute__(self, attr))
        return instances

    def __dir__(self) -> list[str]:
        base = set(super().__dir__())
        for tool in self._tool_instances():
            for name in dir(tool):
                try:
                    member = getattr(tool, name)
                except AttributeError:
                    continue
                if inspect.ismethod(member) and hasattr(member, "__ai_function__"):
                    base.add(name)
        return sorted(base)

    def __getattr__(self, name: str) -> object:
        # __getattr__ is only called when normal lookup fails, so this
        # won't shadow attributes defined directly on the class/instance.
        for tool in self._tool_instances():
            try:
                member = getattr(tool, name)
            except AttributeError:
                continue
            if inspect.ismethod(member) and hasattr(member, "__ai_function__"):
                return member
        msg = f"'{type(self).__name__}' object has no attribute '{name}'"
        raise AttributeError(msg)
