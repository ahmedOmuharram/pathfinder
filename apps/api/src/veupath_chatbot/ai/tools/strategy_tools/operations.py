"""Public AI tool operations for strategy building.

This module composes the public `StrategyTools` class from smaller, purpose-driven
mixins to keep tool implementations easier to navigate.
"""

from __future__ import annotations

from typing import cast

from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.services.strategies.engine.base import StrategyToolsBase

from .attachment_ops import StrategyAttachmentOps
from .discovery_ops import StrategyDiscoveryOps
from .edit_ops import StrategyEditOps
from .graph_ops import StrategyGraphOps
from .step_ops import StrategyStepOps


class StrategyTools(
    StrategyGraphOps,
    StrategyDiscoveryOps,
    StrategyStepOps,  # Provides create_step method
    StrategyEditOps,
    StrategyAttachmentOps,
):
    """Tools for building search strategies.

    This class uses multiple inheritance to compose tool methods from mixins.
    StrategyStepOps provides create_step, which StrategyGraphOps.ensure_single_output uses.


    """

    def __init__(self, session: StrategySession) -> None:
        """Initialize StrategyTools with a session."""
        StrategyToolsBase.__init__(cast(StrategyToolsBase, self), session)
