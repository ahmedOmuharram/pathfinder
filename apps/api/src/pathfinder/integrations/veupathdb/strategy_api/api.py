"""Composed StrategyAPI class.

Aggregates all strategy API mixins into the final :class:`StrategyAPI` class
that callers instantiate.
"""

from pathfinder.integrations.veupathdb.strategy_api.analyses import AnalysisMixin
from pathfinder.integrations.veupathdb.strategy_api.datasets import DatasetsMixin
from pathfinder.integrations.veupathdb.strategy_api.filters import FilterMixin
from pathfinder.integrations.veupathdb.strategy_api.records import RecordsMixin
from pathfinder.integrations.veupathdb.strategy_api.reports import ReportsMixin
from pathfinder.integrations.veupathdb.strategy_api.steps import StepsMixin
from pathfinder.integrations.veupathdb.strategy_api.strategies import (
    StrategiesMixin,
)


class StrategyAPI(
    StepsMixin,
    StrategiesMixin,
    DatasetsMixin,
    ReportsMixin,
    AnalysisMixin,
    FilterMixin,
    RecordsMixin,
):
    """API for creating and managing WDK strategies.

    Provides methods to create steps, compose step trees, build strategies,
    create datasets, run reports, manage filters, execute analyses, and
    fetch records. Follows the WDK REST pattern: create unattached steps,
    then POST a strategy with a stepTree linking them.

    Inherits from :class:`StepsMixin`, :class:`StrategiesMixin`,
    :class:`DatasetsMixin`, :class:`ReportsMixin`, :class:`AnalysisMixin`,
    :class:`FilterMixin`, :class:`RecordsMixin`, and
    :class:`StrategyAPIBase` (via MRO).
    """
