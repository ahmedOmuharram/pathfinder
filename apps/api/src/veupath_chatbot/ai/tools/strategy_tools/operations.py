"""Public AI tool operations for strategy building.

This module composes the public `StrategyTools` class from smaller, purpose-driven
mixins to keep tool implementations easier to navigate.
"""

from __future__ import annotations

from veupath_chatbot.services.strategy_tools.helpers import StrategyToolsHelpers

from .attachment_ops import StrategyAttachmentOps
from .discovery_ops import StrategyDiscoveryOps
from .edit_ops import StrategyEditOps
from .graph_ops import StrategyGraphOps
from .step_ops import StrategyStepOps


class StrategyTools(
    StrategyToolsHelpers,
    StrategyGraphOps,
    StrategyDiscoveryOps,
    StrategyStepOps,
    StrategyEditOps,
    StrategyAttachmentOps,
):
    """Tools for building search strategies."""

    pass