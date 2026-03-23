"""Tests for ExperimentToolsMixin — control test delegation."""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.ai.tools.planner.experiment_tools import ExperimentToolsMixin
from veupath_chatbot.services.control_tests import IntersectionConfig
from veupath_chatbot.services.experiment.types.control_result import (
    ControlSetData,
    ControlTestResult,
)

_SITE_ID = "plasmodb"


class _TestableTools(ExperimentToolsMixin):
    """Concrete subclass for testing."""

    def __init__(self, site_id: str = _SITE_ID) -> None:
        self.site_id = site_id


class TestRunControlTests:
    async def test_delegates_all_args(self) -> None:
        tools = _TestableTools()
        mock_return = ControlTestResult(
            positive=ControlSetData(recall=0.8),
            negative=ControlSetData(false_positive_rate=0.0),
        )

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.experiment_tools.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=mock_return,
            ) as mock_run,
            patch(
                "veupath_chatbot.services.export.get_export_service",
                side_effect=ImportError("skip"),
            ),
        ):
            result = await tools.run_control_tests_on_search(
                record_type="gene",
                target_search_name="GenesByTextSearch",
                target_parameters={"text_expression": "kinase"},
                positive_controls=["PF3D7_0100100"],
                negative_controls=["PF3D7_0200200"],
            )

        assert isinstance(result, dict)
        assert result["positive"]["recall"] == 0.8
        call_args = mock_run.call_args
        cfg: IntersectionConfig = call_args.args[0]
        assert cfg.site_id == _SITE_ID
        assert cfg.record_type == "gene"
        assert cfg.target_search_name == "GenesByTextSearch"
        assert cfg.target_parameters == {"text_expression": "kinase"}
        assert cfg.controls_search_name == "GeneByLocusTag"
        assert cfg.controls_param_name == "ds_gene_ids"
        assert cfg.controls_value_format == "newline"
        assert call_args.kwargs["positive_controls"] == ["PF3D7_0100100"]
        assert call_args.kwargs["negative_controls"] == ["PF3D7_0200200"]

    async def test_defaults_for_optional_args(self) -> None:
        tools = _TestableTools()

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.experiment_tools.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=ControlTestResult(),
            ) as mock_run,
            patch(
                "veupath_chatbot.services.export.get_export_service",
                side_effect=ImportError("skip"),
            ),
        ):
            await tools.run_control_tests_on_search(
                record_type="gene",
                target_search_name="GenesByTextSearch",
                target_parameters={"text_expression": "kinase"},
                positive_controls=["PF3D7_0100100"],
            )

        call_args = mock_run.call_args
        cfg: IntersectionConfig = call_args.args[0]
        assert cfg.controls_search_name == "GeneByLocusTag"
        assert cfg.controls_param_name == "ds_gene_ids"
        assert call_args.kwargs["positive_controls"] == ["PF3D7_0100100"]
        assert call_args.kwargs["negative_controls"] is None
        assert cfg.controls_value_format == "newline"

    async def test_uses_instance_site_id(self) -> None:
        tools = _TestableTools(site_id="toxodb")

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.experiment_tools.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=ControlTestResult(),
            ) as mock_run,
            patch(
                "veupath_chatbot.services.export.get_export_service",
                side_effect=ImportError("skip"),
            ),
        ):
            await tools.run_control_tests_on_search(
                record_type="gene",
                target_search_name="Search",
                target_parameters={},
                positive_controls=["gene1"],
            )

        call_args = mock_run.call_args
        cfg: IntersectionConfig = call_args.args[0]
        assert cfg.site_id == "toxodb"

    async def test_no_controls_returns_error(self) -> None:
        """Without any controls, returns an error."""
        tools = _TestableTools()
        result = await tools.run_control_tests_on_search(
            record_type="gene",
            target_search_name="Search",
            target_parameters={},
        )
        assert result.get("ok") is False

    async def test_wdk_step_id_mode(self) -> None:
        """When wdk_step_id is provided, uses step-based control tests."""
        tools = _TestableTools()

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.experiment_tools._run_step_control_tests",
                new_callable=AsyncMock,
                return_value={"wdkStepId": 100, "positive": {"recall": 1.0}},
            ) as mock_step,
            patch(
                "veupath_chatbot.services.export.get_export_service",
                side_effect=ImportError("skip"),
            ),
        ):
            result = await tools.run_control_tests_on_step(
                wdk_step_id=100,
                positive_controls=["PF3D7_0100100"],
            )

        mock_step.assert_awaited_once()
        assert result["wdkStepId"] == 100
