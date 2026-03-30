"""Public AI tool operations for strategy building.

This module composes the public `StrategyTools` class from smaller, purpose-driven
mixins to keep tool implementations easier to navigate.
"""

from typing import cast

from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.services.strategies.engine.base import StrategyToolsBase

from .attachment_ops import StrategyAttachmentOps
from .edit_ops import StrategyEditOps
from .graph_ops import StrategyGraphOps
from .step_ops import StrategyStepOps


class StrategyTools(
    StrategyGraphOps,
    StrategyStepOps,
    StrategyEditOps,
    StrategyAttachmentOps,
):
    """Tools for building search strategies.

    Composes tool methods from purpose-driven mixins.
    """

    def __init__(self, session: StrategySession) -> None:
        """Initialize StrategyTools with a session."""
        StrategyToolsBase.__init__(cast("StrategyToolsBase", self), session)
