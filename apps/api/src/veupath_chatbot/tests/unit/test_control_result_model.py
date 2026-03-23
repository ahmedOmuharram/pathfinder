"""Tests for ControlTestResult, ControlSetData, and ControlTargetData models."""

from veupath_chatbot.services.experiment.types.control_result import (
    ControlSetData,
    ControlTargetData,
    ControlTestResult,
)

# ---------------------------------------------------------------------------
# ControlTargetData
# ---------------------------------------------------------------------------


class TestControlTargetData:
    def test_defaults(self) -> None:
        target = ControlTargetData()
        assert target.search_name == ""
        assert target.parameters == {}
        assert target.step_id is None
        assert target.estimated_size is None

    def test_from_camel_case_dict(self) -> None:
        data = {
            "searchName": "GenesByTaxon",
            "parameters": {"organism": "Plasmodium falciparum 3D7"},
            "stepId": 42,
            "estimatedSize": 100,
        }
        target = ControlTargetData.model_validate(data)
        assert target.search_name == "GenesByTaxon"
        assert target.parameters == {"organism": "Plasmodium falciparum 3D7"}
        assert target.step_id == 42
        assert target.estimated_size == 100


# ---------------------------------------------------------------------------
# ControlSetData
# ---------------------------------------------------------------------------


class TestControlSetData:
    def test_defaults(self) -> None:
        csd = ControlSetData()
        assert csd.controls_count == 0
        assert csd.intersection_count == 0
        assert csd.intersection_ids == []
        assert csd.intersection_ids_sample == []
        assert csd.target_step_id is None
        assert csd.target_estimated_size == 0
        assert csd.missing_ids_sample == []
        assert csd.unexpected_hits_sample == []
        assert csd.recall is None
        assert csd.false_positive_rate is None

    def test_from_camel_case_dict(self) -> None:
        data = {
            "controlsCount": 50,
            "intersectionCount": 10,
            "intersectionIds": ["gene1", "gene2"],
            "intersectionIdsSample": ["gene1"],
            "targetStepId": 7,
            "targetEstimatedSize": 200,
            "missingIdsSample": ["gene3"],
            "recall": 0.85,
        }
        csd = ControlSetData.model_validate(data)
        assert csd.controls_count == 50
        assert csd.intersection_count == 10
        assert csd.intersection_ids == ["gene1", "gene2"]
        assert csd.intersection_ids_sample == ["gene1"]
        assert csd.target_step_id == 7
        assert csd.target_estimated_size == 200
        assert csd.missing_ids_sample == ["gene3"]
        assert csd.recall == 0.85
        assert csd.unexpected_hits_sample == []
        assert csd.false_positive_rate is None


# ---------------------------------------------------------------------------
# ControlTestResult
# ---------------------------------------------------------------------------


class TestControlTestResult:
    def test_defaults(self) -> None:
        result = ControlTestResult()
        assert result.site_id == ""
        assert result.record_type == ""
        assert isinstance(result.target, ControlTargetData)
        assert result.target.search_name == ""
        assert result.positive is None
        assert result.negative is None

    def test_full_result_with_both_controls(self) -> None:
        data = {
            "siteId": "plasmodb.org",
            "recordType": "transcript",
            "target": {
                "searchName": "GenesByTaxon",
                "parameters": {"organism": "Plasmodium falciparum 3D7"},
                "stepId": 1,
                "estimatedSize": 500,
            },
            "positive": {
                "controlsCount": 20,
                "intersectionCount": 15,
                "intersectionIds": ["g1", "g2", "g3"],
                "intersectionIdsSample": ["g1", "g2"],
                "targetStepId": 1,
                "targetEstimatedSize": 500,
                "missingIdsSample": ["g4", "g5"],
                "recall": 0.75,
            },
            "negative": {
                "controlsCount": 30,
                "intersectionCount": 2,
                "intersectionIds": ["g10", "g11"],
                "intersectionIdsSample": ["g10"],
                "targetStepId": 1,
                "targetEstimatedSize": 500,
                "unexpectedHitsSample": ["g10", "g11"],
                "falsePositiveRate": 0.067,
            },
        }
        result = ControlTestResult.model_validate(data)
        assert result.site_id == "plasmodb.org"
        assert result.record_type == "transcript"
        assert result.target.search_name == "GenesByTaxon"
        assert result.target.step_id == 1
        assert result.target.estimated_size == 500

        assert result.positive is not None
        assert result.positive.controls_count == 20
        assert result.positive.intersection_count == 15
        assert result.positive.recall == 0.75
        assert result.positive.missing_ids_sample == ["g4", "g5"]

        assert result.negative is not None
        assert result.negative.controls_count == 30
        assert result.negative.intersection_count == 2
        assert result.negative.false_positive_rate == 0.067
        assert result.negative.unexpected_hits_sample == ["g10", "g11"]

    def test_no_controls(self) -> None:
        data = {
            "siteId": "toxodb.org",
            "recordType": "transcript",
            "target": {
                "searchName": "GenesByLocation",
                "parameters": {},
            },
            "positive": None,
            "negative": None,
        }
        result = ControlTestResult.model_validate(data)
        assert result.site_id == "toxodb.org"
        assert result.positive is None
        assert result.negative is None

    def test_camel_case_alias_resolution(self) -> None:
        """Verify camelCase aliases resolve to snake_case attributes."""
        data = {
            "siteId": "fungidb.org",
            "recordType": "transcript",
            "target": {
                "searchName": "GenesByGoTerm",
                "parameters": {"goTerm": "GO:0006915"},
                "stepId": 99,
                "estimatedSize": 42,
            },
            "positive": {
                "controlsCount": 5,
                "intersectionCount": 3,
                "intersectionIds": ["a", "b", "c"],
                "intersectionIdsSample": ["a"],
                "targetStepId": 99,
                "targetEstimatedSize": 42,
                "missingIdsSample": ["d"],
                "recall": 0.6,
            },
        }
        result = ControlTestResult.model_validate(data)
        # Top-level camelCase -> snake_case
        assert result.site_id == "fungidb.org"
        assert result.record_type == "transcript"
        # Nested target camelCase -> snake_case
        assert result.target.search_name == "GenesByGoTerm"
        assert result.target.step_id == 99
        assert result.target.estimated_size == 42
        # Nested positive camelCase -> snake_case
        assert result.positive is not None
        assert result.positive.controls_count == 5
        assert result.positive.intersection_count == 3
        assert result.positive.intersection_ids_sample == ["a"]
        assert result.positive.target_step_id == 99
        assert result.positive.target_estimated_size == 42
        assert result.positive.missing_ids_sample == ["d"]
        assert result.positive.recall == 0.6
