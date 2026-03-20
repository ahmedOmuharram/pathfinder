"""Tests verifying the reports.py split into focused mixins.

Each mixin class exists and exposes the expected methods.
"""

import inspect

from veupath_chatbot.integrations.veupathdb.strategy_api.analyses import AnalysisMixin
from veupath_chatbot.integrations.veupathdb.strategy_api.api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.integrations.veupathdb.strategy_api.filters import FilterMixin
from veupath_chatbot.integrations.veupathdb.strategy_api.records import RecordsMixin
from veupath_chatbot.integrations.veupathdb.strategy_api.reports import ReportsMixin


class TestMixinClassesExist:
    """All four mixin classes exist and inherit from StrategyAPIBase."""

    def test_reports_mixin_exists(self) -> None:
        assert issubclass(ReportsMixin, StrategyAPIBase)

    def test_analysis_mixin_exists(self) -> None:
        assert issubclass(AnalysisMixin, StrategyAPIBase)

    def test_filter_mixin_exists(self) -> None:
        assert issubclass(FilterMixin, StrategyAPIBase)

    def test_records_mixin_exists(self) -> None:
        assert issubclass(RecordsMixin, StrategyAPIBase)


class TestReportsMixinMethods:
    """ReportsMixin has core report methods."""

    def test_has_run_step_report(self) -> None:
        assert hasattr(ReportsMixin, "run_step_report")
        assert inspect.iscoroutinefunction(ReportsMixin.run_step_report)

    def test_has_get_step_answer(self) -> None:
        assert hasattr(ReportsMixin, "get_step_answer")
        assert inspect.iscoroutinefunction(ReportsMixin.get_step_answer)

    def test_has_get_step_records(self) -> None:
        assert hasattr(ReportsMixin, "get_step_records")
        assert inspect.iscoroutinefunction(ReportsMixin.get_step_records)

    def test_has_get_step_count(self) -> None:
        assert hasattr(ReportsMixin, "get_step_count")
        assert inspect.iscoroutinefunction(ReportsMixin.get_step_count)

    def test_does_not_have_filter_methods(self) -> None:
        assert not hasattr(ReportsMixin, "set_step_filter")
        assert not hasattr(ReportsMixin, "delete_step_filter")
        assert not hasattr(ReportsMixin, "list_step_filters")

    def test_does_not_have_analysis_methods(self) -> None:
        assert not hasattr(ReportsMixin, "run_step_analysis")
        assert not hasattr(ReportsMixin, "list_analysis_types")

    def test_does_not_have_record_type_methods(self) -> None:
        assert not hasattr(ReportsMixin, "get_record_type_info")
        assert not hasattr(ReportsMixin, "get_single_record")


class TestAnalysisMixinMethods:
    """AnalysisMixin has analysis lifecycle methods."""

    def test_has_list_analysis_types(self) -> None:
        assert hasattr(AnalysisMixin, "list_analysis_types")
        assert inspect.iscoroutinefunction(AnalysisMixin.list_analysis_types)

    def test_has_get_analysis_type(self) -> None:
        assert hasattr(AnalysisMixin, "get_analysis_type")
        assert inspect.iscoroutinefunction(AnalysisMixin.get_analysis_type)

    def test_has_list_step_analyses(self) -> None:
        assert hasattr(AnalysisMixin, "list_step_analyses")
        assert inspect.iscoroutinefunction(AnalysisMixin.list_step_analyses)

    def test_has_run_step_analysis(self) -> None:
        assert hasattr(AnalysisMixin, "run_step_analysis")
        assert inspect.iscoroutinefunction(AnalysisMixin.run_step_analysis)

    def test_has_warmup_step(self) -> None:
        assert hasattr(AnalysisMixin, "_warmup_step")
        assert inspect.iscoroutinefunction(AnalysisMixin._warmup_step)

    def test_has_create_analysis(self) -> None:
        assert hasattr(AnalysisMixin, "_create_analysis")
        assert inspect.iscoroutinefunction(AnalysisMixin._create_analysis)

    def test_has_poll_analysis(self) -> None:
        assert hasattr(AnalysisMixin, "_poll_analysis")
        assert inspect.iscoroutinefunction(AnalysisMixin._poll_analysis)


class TestFilterMixinMethods:
    """FilterMixin has filter CRUD methods."""

    def test_has_set_step_filter(self) -> None:
        assert hasattr(FilterMixin, "set_step_filter")
        assert inspect.iscoroutinefunction(FilterMixin.set_step_filter)

    def test_has_delete_step_filter(self) -> None:
        assert hasattr(FilterMixin, "delete_step_filter")
        assert inspect.iscoroutinefunction(FilterMixin.delete_step_filter)

    def test_has_list_step_filters(self) -> None:
        assert hasattr(FilterMixin, "list_step_filters")
        assert inspect.iscoroutinefunction(FilterMixin.list_step_filters)


class TestRecordsMixinMethods:
    """RecordsMixin has record type and single record methods."""

    def test_has_get_record_type_info(self) -> None:
        assert hasattr(RecordsMixin, "get_record_type_info")
        assert inspect.iscoroutinefunction(RecordsMixin.get_record_type_info)

    def test_has_get_single_record(self) -> None:
        assert hasattr(RecordsMixin, "get_single_record")
        assert inspect.iscoroutinefunction(RecordsMixin.get_single_record)

    def test_has_get_column_distribution(self) -> None:
        assert hasattr(RecordsMixin, "get_column_distribution")
        assert inspect.iscoroutinefunction(RecordsMixin.get_column_distribution)


class TestStrategyAPIComposition:
    """StrategyAPI inherits from all four mixins."""

    def test_strategy_api_inherits_all_mixins(self) -> None:
        assert issubclass(StrategyAPI, ReportsMixin)
        assert issubclass(StrategyAPI, AnalysisMixin)
        assert issubclass(StrategyAPI, FilterMixin)
        assert issubclass(StrategyAPI, RecordsMixin)
