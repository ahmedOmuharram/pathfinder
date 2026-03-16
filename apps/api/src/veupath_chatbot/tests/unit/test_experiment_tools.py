"""Tests for ExperimentToolsMixin — control test delegation."""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.ai.tools.planner.experiment_tools import ExperimentToolsMixin

_SITE_ID = "plasmodb"


class _TestableTools(ExperimentToolsMixin):
    """Concrete subclass for testing."""

    def __init__(self, site_id: str = _SITE_ID) -> None:
        self.site_id = site_id


class TestRunControlTests:
    async def test_delegates_all_args(self) -> None:
        tools = _TestableTools()
        expected = {"positiveRecall": 0.8, "negativeExclusion": 1.0}

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.experiment_tools.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=expected,
            ) as mock_run,
            patch(
                "veupath_chatbot.services.export.get_export_service",
                side_effect=ImportError("skip"),
            ),
        ):
            result = await tools.run_control_tests(
                record_type="gene",
                target_search_name="GenesByTextSearch",
                target_parameters={"text_expression": "kinase"},
                controls_search_name="GeneByLocusTag",
                controls_param_name="ds_gene_ids",
                positive_controls=["PF3D7_0100100"],
                negative_controls=["PF3D7_0200200"],
                controls_value_format="newline",
                controls_extra_parameters={"organism": "P. falciparum 3D7"},
                id_field="gene_source_id",
            )

        assert result == expected
        mock_run.assert_awaited_once_with(
            site_id=_SITE_ID,
            record_type="gene",
            target_search_name="GenesByTextSearch",
            target_parameters={"text_expression": "kinase"},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            positive_controls=["PF3D7_0100100"],
            negative_controls=["PF3D7_0200200"],
            controls_value_format="newline",
            controls_extra_parameters={"organism": "P. falciparum 3D7"},
            id_field="gene_source_id",
        )

    async def test_defaults_for_optional_args(self) -> None:
        tools = _TestableTools()

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.experiment_tools.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value={},
            ) as mock_run,
            patch(
                "veupath_chatbot.services.export.get_export_service",
                side_effect=ImportError("skip"),
            ),
        ):
            await tools.run_control_tests(
                record_type="gene",
                target_search_name="GenesByTextSearch",
                target_parameters={"text_expression": "kinase"},
                positive_controls=["PF3D7_0100100"],
            )

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["controls_search_name"] == "GeneByLocusTag"
        assert call_kwargs["controls_param_name"] == "ds_gene_ids"
        assert call_kwargs["positive_controls"] == ["PF3D7_0100100"]
        assert call_kwargs["negative_controls"] is None
        assert call_kwargs["controls_value_format"] == "newline"

    async def test_none_target_parameters_becomes_empty_dict(self) -> None:
        """target_parameters or {} ensures None is converted to empty dict."""
        tools = _TestableTools()

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.experiment_tools.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value={},
            ) as mock_run,
            patch(
                "veupath_chatbot.services.export.get_export_service",
                side_effect=ImportError("skip"),
            ),
        ):
            await tools.run_control_tests(
                record_type="gene",
                target_search_name="GenesByTextSearch",
                target_parameters=None,
                positive_controls=["PF3D7_0100100"],
            )

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["target_parameters"] == {}

    async def test_uses_instance_site_id(self) -> None:
        tools = _TestableTools(site_id="toxodb")

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.experiment_tools.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value={},
            ) as mock_run,
            patch(
                "veupath_chatbot.services.export.get_export_service",
                side_effect=ImportError("skip"),
            ),
        ):
            await tools.run_control_tests(
                record_type="gene",
                target_search_name="Search",
                target_parameters={},
                controls_search_name="CtrlSearch",
                controls_param_name="ids",
                positive_controls=["gene1"],
            )

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["site_id"] == "toxodb"

    async def test_no_controls_returns_error(self) -> None:
        """Without any controls, returns an error."""
        tools = _TestableTools()
        result = await tools.run_control_tests(
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
            result = await tools.run_control_tests(
                record_type="gene",
                wdk_step_id=100,
                positive_controls=["PF3D7_0100100"],
            )

        mock_step.assert_awaited_once()
        assert result["wdkStepId"] == 100
