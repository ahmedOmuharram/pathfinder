"""Composed StrategyAPI class.

Aggregates all strategy API mixins into the final :class:`StrategyAPI` class
that callers instantiate.
"""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.strategy_api.reports import ReportsMixin
from veupath_chatbot.integrations.veupathdb.strategy_api.steps import StepsMixin
from veupath_chatbot.integrations.veupathdb.strategy_api.strategies import (
    StrategiesMixin,
)


class StrategyAPI(StepsMixin, StrategiesMixin, ReportsMixin):
    """API for creating and managing WDK strategies.

    Provides methods to create steps, compose step trees, build strategies,
    run reports, and manage datasets. Follows the WDK REST pattern:
    create unattached steps, then POST a strategy with a stepTree linking them.

    Inherits from :class:`StepsMixin`, :class:`StrategiesMixin`,
    :class:`ReportsMixin`, and :class:`StrategyAPIBase` (via MRO).
    """

    pass
