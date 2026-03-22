"""Unit tests for WDK structural response models.

Verifies parsing, field defaults, immutability, camelCase alias handling,
and nested model composition for all models in ``wdk_models.py``.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKDatasetConfig,
    WDKDatasetConfigBasket,
    WDKDatasetConfigFile,
    WDKDatasetConfigIdList,
    WDKDatasetConfigStrategy,
    WDKDatasetConfigUrl,
    WDKFilterValue,
    WDKIdentifier,
    WDKRecordInstance,
    WDKRecordType,
    WDKSearch,
    WDKSearchConfig,
    WDKSearchResponse,
    WDKSortSpec,
    WDKStep,
    WDKStepAnalysisConfig,
    WDKStepAnalysisType,
    WDKStepTree,
    WDKStrategyDetails,
    WDKStrategySummary,
    WDKUserInfo,
    WDKValidation,
)
from veupath_chatbot.tests.fixtures.wdk_responses import (
    search_details_response,
    wdk_answer_json,
    wdk_record_type_json,
    wdk_step_json,
    wdk_strategy_details_json,
    wdk_strategy_summary_json,
    wdk_validation_json,
)


# ---------------------------------------------------------------------------
# TestWDKModel — base class behaviour
# ---------------------------------------------------------------------------
class TestWDKModel:
    """Tests for the WDKModel base class configuration."""

    def test_frozen_prevents_mutation(self) -> None:
        v = WDKValidation.model_validate({"level": "RUNNABLE", "isValid": True})
        with pytest.raises(ValidationError):
            v.is_valid = False

    def test_extra_fields_ignored(self) -> None:
        v = WDKValidation.model_validate(
            {"level": "RUNNABLE", "isValid": True, "unknownField": 42},
        )
        assert v.level == "RUNNABLE"
        assert not hasattr(v, "unknownField")
        assert not hasattr(v, "unknown_field")

    def test_camel_case_aliases(self) -> None:
        s = WDKSortSpec.model_validate(
            {"attributeName": "gene_id", "direction": "ASC"},
        )
        assert s.attribute_name == "gene_id"

    def test_populate_by_name(self) -> None:
        s = WDKSortSpec(attribute_name="gene_id", direction="ASC")
        assert s.attribute_name == "gene_id"
        assert s.direction == "ASC"


# ---------------------------------------------------------------------------
# TestWDKSearchConfig
# ---------------------------------------------------------------------------
class TestWDKSearchConfig:
    """Tests for WDKSearchConfig parsing and defaults."""

    def test_parse_minimal(self) -> None:
        cfg = WDKSearchConfig.model_validate(
            {"parameters": {"organism": '["Pf3D7"]'}},
        )
        assert cfg.parameters == {"organism": '["Pf3D7"]'}
        assert cfg.wdk_weight == 0

    def test_parse_with_filters(self) -> None:
        cfg = WDKSearchConfig.model_validate(
            {
                "parameters": {},
                "filters": [{"name": "matched_result", "value": "Y"}],
            },
        )
        assert len(cfg.filters) == 1
        assert isinstance(cfg.filters[0], WDKFilterValue)
        assert cfg.filters[0].name == "matched_result"

    def test_parse_with_view_filters(self) -> None:
        cfg = WDKSearchConfig.model_validate(
            {
                "parameters": {},
                "viewFilters": [{"name": "gene_boolean_filter", "value": True}],
            },
        )
        assert len(cfg.view_filters) == 1
        assert cfg.view_filters[0].name == "gene_boolean_filter"

    def test_parameters_are_string_values(self) -> None:
        cfg = WDKSearchConfig.model_validate(
            {"parameters": {"organism": '["Plasmodium falciparum 3D7"]'}},
        )
        assert isinstance(cfg.parameters, dict)
        assert cfg.parameters["organism"] == '["Plasmodium falciparum 3D7"]'

    def test_default_wdk_weight_zero(self) -> None:
        cfg = WDKSearchConfig.model_validate({"parameters": {}})
        assert cfg.wdk_weight == 0

    def test_frozen_immutability(self) -> None:
        cfg = WDKSearchConfig.model_validate({"parameters": {"a": "b"}})
        with pytest.raises(ValidationError):
            cfg.parameters = {}


# ---------------------------------------------------------------------------
# TestWDKValidation
# ---------------------------------------------------------------------------
class TestWDKValidation:
    """Tests for WDKValidation parsing and defaults."""

    def test_parse_valid(self) -> None:
        v = WDKValidation.model_validate(wdk_validation_json())
        assert v.level == "RUNNABLE"
        assert v.is_valid is True

    def test_parse_invalid_with_errors(self) -> None:
        v = WDKValidation.model_validate(wdk_validation_json(is_valid=False))
        assert v.is_valid is False
        assert v.errors is not None
        assert isinstance(v.errors.general, list)

    def test_default_is_valid(self) -> None:
        v = WDKValidation.model_validate({})
        assert v.is_valid is True
        assert v.level == "NONE"

    def test_errors_absent_when_valid(self) -> None:
        v = WDKValidation.model_validate(wdk_validation_json())
        assert v.errors is None


# ---------------------------------------------------------------------------
# TestWDKStepTree
# ---------------------------------------------------------------------------
class TestWDKStepTree:
    """Tests for WDKStepTree recursive parsing."""

    def test_parse_leaf_step(self) -> None:
        tree = WDKStepTree.model_validate({"stepId": 100})
        assert tree.step_id == 100
        assert tree.primary_input is None
        assert tree.secondary_input is None

    def test_parse_two_level_tree(self) -> None:
        tree = WDKStepTree.model_validate(
            {"stepId": 200, "primaryInput": {"stepId": 100}},
        )
        assert tree.step_id == 200
        assert tree.primary_input is not None
        assert tree.primary_input.step_id == 100

    def test_parse_three_level_tree(self) -> None:
        tree = WDKStepTree.model_validate(
            {
                "stepId": 300,
                "primaryInput": {"stepId": 200},
                "secondaryInput": {"stepId": 100},
            },
        )
        assert tree.step_id == 300
        assert tree.primary_input is not None
        assert tree.primary_input.step_id == 200
        assert tree.secondary_input is not None
        assert tree.secondary_input.step_id == 100

    def test_recursive_depth(self) -> None:
        tree = WDKStepTree.model_validate(
            {
                "stepId": 400,
                "primaryInput": {
                    "stepId": 300,
                    "primaryInput": {
                        "stepId": 200,
                        "primaryInput": {"stepId": 100},
                    },
                },
            },
        )
        assert tree.step_id == 400
        level1 = tree.primary_input
        assert level1 is not None
        assert level1.step_id == 300
        level2 = level1.primary_input
        assert level2 is not None
        assert level2.step_id == 200
        level3 = level2.primary_input
        assert level3 is not None
        assert level3.step_id == 100

    def test_null_inputs_treated_as_none(self) -> None:
        tree = WDKStepTree.model_validate(
            {"stepId": 100, "primaryInput": None, "secondaryInput": None},
        )
        assert tree.primary_input is None
        assert tree.secondary_input is None


# ---------------------------------------------------------------------------
# TestWDKStep
# ---------------------------------------------------------------------------
class TestWDKStep:
    """Tests for WDKStep parsing from realistic WDK JSON."""

    def test_parse_from_fixture(self) -> None:
        step = WDKStep.model_validate(wdk_step_json())
        assert step.id == 12345
        assert step.search_name == "GenesByTaxon"

    def test_nullable_estimated_size(self) -> None:
        step = WDKStep.model_validate(wdk_step_json(estimated_size=None))
        assert step.estimated_size is None

    def test_nullable_strategy_id(self) -> None:
        step = WDKStep.model_validate(wdk_step_json(strategy_id=None))
        assert step.strategy_id is None

    def test_nullable_record_class_name(self) -> None:
        data = wdk_step_json()
        data["recordClassName"] = None
        step = WDKStep.model_validate(data)
        assert step.record_class_name is None

    def test_expanded_key_not_is_expanded(self) -> None:
        """The WDK JSON key is 'expanded', not 'isExpanded'."""
        step = WDKStep.model_validate(wdk_step_json())
        assert step.expanded is False

    def test_extra_fields_ignored(self) -> None:
        data = wdk_step_json()
        data["totallyUnknownField"] = "should be ignored"
        step = WDKStep.model_validate(data)
        assert step.id == 12345
        assert not hasattr(step, "totallyUnknownField")

    def test_search_config_nested(self) -> None:
        step = WDKStep.model_validate(wdk_step_json())
        assert isinstance(step.search_config, WDKSearchConfig)
        assert isinstance(step.search_config.parameters, dict)

    def test_validation_nested(self) -> None:
        step = WDKStep.model_validate(wdk_step_json())
        assert isinstance(step.validation, WDKValidation)


# ---------------------------------------------------------------------------
# TestWDKStrategySummary
# ---------------------------------------------------------------------------
class TestWDKStrategySummary:
    """Tests for WDKStrategySummary parsing."""

    def test_parse_from_fixture(self) -> None:
        summary = WDKStrategySummary.model_validate(
            wdk_strategy_summary_json(),
        )
        assert summary.strategy_id == 99999
        assert summary.name == "Test Strategy"

    def test_estimated_size_as_number(self) -> None:
        summary = WDKStrategySummary.model_validate(
            wdk_strategy_summary_json(),
        )
        assert summary.estimated_size == 150

    def test_nullable_record_class_name(self) -> None:
        summary = WDKStrategySummary.model_validate(
            wdk_strategy_summary_json(record_class_name=None),
        )
        assert summary.record_class_name is None

    def test_last_viewed_field_name(self) -> None:
        """WDK uses 'lastViewed', not 'lastViewTime'."""
        data = wdk_strategy_summary_json()
        data["lastViewed"] = "2026-01-01"
        summary = WDKStrategySummary.model_validate(data)
        assert summary.last_viewed == "2026-01-01"


# ---------------------------------------------------------------------------
# TestWDKStrategyDetails
# ---------------------------------------------------------------------------
class TestWDKStrategyDetails:
    """Tests for WDKStrategyDetails (extends WDKStrategySummary)."""

    def test_parse_with_step_tree(self) -> None:
        details = WDKStrategyDetails.model_validate(
            wdk_strategy_details_json(),
        )
        assert details.step_tree.step_id == 12345

    def test_steps_map_string_keys(self) -> None:
        details = WDKStrategyDetails.model_validate(
            wdk_strategy_details_json(),
        )
        assert "12345" in details.steps

    def test_steps_parsed_as_wdk_step(self) -> None:
        details = WDKStrategyDetails.model_validate(
            wdk_strategy_details_json(),
        )
        assert isinstance(details.steps["12345"], WDKStep)

    def test_inherits_summary_fields(self) -> None:
        details = WDKStrategyDetails.model_validate(
            wdk_strategy_details_json(),
        )
        assert details.strategy_id == 99999
        assert details.name == "Test Strategy"
        assert details.root_step_id == 12345

    def test_validation_on_details(self) -> None:
        details = WDKStrategyDetails.model_validate(
            wdk_strategy_details_json(),
        )
        assert details.validation is not None


# ---------------------------------------------------------------------------
# TestWDKSearch
# ---------------------------------------------------------------------------
class TestWDKSearch:
    """Tests for WDKSearch parsing from list and detail endpoints."""

    def test_parse_from_list_element(self) -> None:
        """List endpoint searches omit the 'parameters' key."""
        data = {
            "urlSegment": "GenesByTaxon",
            "fullName": "GeneQuestions.GenesByTaxon",
            "queryName": "GenesByTaxon",
            "displayName": "Organism",
            "shortDisplayName": "Organism",
            "outputRecordClassName": "transcript",
            "paramNames": ["organism"],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "organism"],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        }
        search = WDKSearch.model_validate(data)
        assert search.url_segment == "GenesByTaxon"
        assert search.parameters is None

    def test_parse_with_expanded_params(self) -> None:
        envelope = search_details_response()
        search = WDKSearch.model_validate(envelope["searchData"])
        assert search.parameters is not None
        assert isinstance(search.parameters, list)
        assert len(search.parameters) > 0

    def test_parameters_none_when_absent(self) -> None:
        data = {
            "urlSegment": "GenesByTextSearch",
            "fullName": "GeneQuestions.GenesByTextSearch",
            "queryName": "GenesByTextSearch",
            "displayName": "Text search (genes)",
            "shortDisplayName": "Text",
            "outputRecordClassName": "transcript",
            "paramNames": ["text_expression"],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": [],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        }
        search = WDKSearch.model_validate(data)
        assert search.parameters is None

    def test_param_names_always_present(self) -> None:
        data = {
            "urlSegment": "GenesByTaxon",
            "paramNames": ["organism"],
        }
        search = WDKSearch.model_validate(data)
        assert isinstance(search.param_names, list)
        assert "organism" in search.param_names

    def test_new_build_is_string(self) -> None:
        envelope = search_details_response()
        search = WDKSearch.model_validate(envelope["searchData"])
        assert isinstance(search.new_build, str)

    def test_optional_allowed_input_types(self) -> None:
        """Boolean searches have allowed input class names; normal searches do not."""
        boolean_data = {
            "urlSegment": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
            "allowedPrimaryInputRecordClassNames": ["transcript"],
            "allowedSecondaryInputRecordClassNames": ["transcript"],
            "paramNames": [],
        }
        boolean_search = WDKSearch.model_validate(boolean_data)
        assert boolean_search.allowed_primary_input_record_class_names is not None
        assert isinstance(
            boolean_search.allowed_primary_input_record_class_names, list,
        )

        normal_data = {
            "urlSegment": "GenesByTaxon",
            "paramNames": [],
        }
        normal_search = WDKSearch.model_validate(normal_data)
        assert normal_search.allowed_primary_input_record_class_names is None

    def test_extra_fields_ignored(self) -> None:
        data = {
            "urlSegment": "GenesByTaxon",
            "unknownField": "should be dropped",
        }
        search = WDKSearch.model_validate(data)
        assert search.url_segment == "GenesByTaxon"
        assert not hasattr(search, "unknownField")
        assert not hasattr(search, "unknown_field")


# ---------------------------------------------------------------------------
# TestWDKSearchResponse
# ---------------------------------------------------------------------------
class TestWDKSearchResponse:
    """Tests for WDKSearchResponse envelope parsing."""

    def test_parse_envelope(self) -> None:
        resp = WDKSearchResponse.model_validate(search_details_response())
        assert isinstance(resp.search_data, WDKSearch)
        assert isinstance(resp.validation, WDKValidation)

    def test_access_search_data(self) -> None:
        resp = WDKSearchResponse.model_validate(search_details_response())
        assert resp.search_data.url_segment == "GenesByTaxon"

    def test_access_validation(self) -> None:
        resp = WDKSearchResponse.model_validate(search_details_response())
        assert resp.validation.is_valid is True

    def test_replaces_unwrap_search_data(self) -> None:
        """The raw JSON has 'searchData' key; the model maps it to search_data."""
        raw = search_details_response()
        assert "searchData" in raw
        resp = WDKSearchResponse.model_validate(raw)
        assert resp.search_data.url_segment == "GenesByTaxon"


# ---------------------------------------------------------------------------
# TestWDKRecordType
# ---------------------------------------------------------------------------
class TestWDKRecordType:
    """Tests for WDKRecordType parsing."""

    def test_parse_with_searches(self) -> None:
        search_data = {
            "urlSegment": "GenesByTaxon",
            "fullName": "GeneQuestions.GenesByTaxon",
            "queryName": "GenesByTaxon",
            "displayName": "Organism",
            "shortDisplayName": "Organism",
            "outputRecordClassName": "transcript",
            "paramNames": ["organism"],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": [],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        }
        rt = WDKRecordType.model_validate(
            wdk_record_type_json(searches=[search_data]),
        )
        assert rt.searches is not None
        assert len(rt.searches) == 1

    def test_parse_without_searches(self) -> None:
        rt = WDKRecordType.model_validate(wdk_record_type_json())
        assert rt.searches is None

    def test_url_segment_is_canonical(self) -> None:
        rt = WDKRecordType.model_validate(wdk_record_type_json())
        assert rt.url_segment == "transcript"


# ---------------------------------------------------------------------------
# TestWDKAnswer
# ---------------------------------------------------------------------------
class TestWDKAnswer:
    """Tests for WDKAnswer parsing."""

    def test_parse_answer_with_records(self) -> None:
        answer = WDKAnswer.model_validate(wdk_answer_json())
        assert isinstance(answer.records, list)
        assert len(answer.records) > 0

    def test_meta_total_count(self) -> None:
        answer = WDKAnswer.model_validate(wdk_answer_json())
        assert answer.meta.total_count == 5432

    def test_records_are_json_objects(self) -> None:
        answer = WDKAnswer.model_validate(wdk_answer_json())
        for record in answer.records:
            assert isinstance(record, dict)

    def test_empty_records_default(self) -> None:
        answer = WDKAnswer.model_validate(
            {
                "meta": {
                    "totalCount": 0,
                    "responseCount": 0,
                    "displayTotalCount": 0,
                    "viewTotalCount": 0,
                    "displayViewTotalCount": 0,
                    "recordClassName": "transcript",
                    "attributes": [],
                    "tables": [],
                },
            },
        )
        assert answer.records == []


# ---------------------------------------------------------------------------
# TestWDKIdentifier
# ---------------------------------------------------------------------------
class TestWDKIdentifier:
    """Tests for WDKIdentifier (replaces WDKStrategyCreateResponse)."""

    def test_parse_from_camel_case(self) -> None:
        ident = WDKIdentifier.model_validate({"id": 42})
        assert ident.id == 42

    def test_same_shape_as_strategy_create_response(self) -> None:
        """WDKIdentifier has the same shape as the old WDKStrategyCreateResponse."""
        ident = WDKIdentifier.model_validate({"id": 99999})
        assert ident.id == 99999

    def test_extra_fields_ignored(self) -> None:
        ident = WDKIdentifier.model_validate({"id": 1, "unknownField": "x"})
        assert ident.id == 1
        assert not hasattr(ident, "unknownField")

    def test_frozen(self) -> None:
        ident = WDKIdentifier.model_validate({"id": 1})
        with pytest.raises(ValidationError):
            ident.id = 2


# ---------------------------------------------------------------------------
# TestWDKStepAnalysisType
# ---------------------------------------------------------------------------
class TestWDKStepAnalysisType:
    """Tests for WDKStepAnalysisType parsing."""

    def test_parse_from_camel_case(self) -> None:
        sat = WDKStepAnalysisType.model_validate({
            "name": "word-enrichment",
            "displayName": "Word Enrichment",
            "shortDescription": "Find enriched words in gene descriptions",
            "description": "Detailed description here",
            "releaseVersion": "62",
            "customThumbnail": "/img/thumb.png",
            "paramNames": ["pValueCutoff", "organism"],
            "groups": [
                {
                    "name": "main",
                    "displayName": "Main",
                    "description": "",
                    "isVisible": True,
                    "displayType": "",
                    "parameters": ["pValueCutoff"],
                },
            ],
        })
        assert sat.name == "word-enrichment"
        assert sat.display_name == "Word Enrichment"
        assert sat.short_description == "Find enriched words in gene descriptions"
        assert sat.description == "Detailed description here"
        assert sat.release_version == "62"
        assert sat.custom_thumbnail == "/img/thumb.png"
        assert sat.param_names == ["pValueCutoff", "organism"]
        assert len(sat.groups) == 1
        assert sat.groups[0].name == "main"

    def test_defaults(self) -> None:
        sat = WDKStepAnalysisType.model_validate({
            "name": "go-enrichment",
            "displayName": "GO Enrichment",
        })
        assert sat.short_description == ""
        assert sat.description == ""
        assert sat.release_version == ""
        assert sat.custom_thumbnail is None
        assert sat.param_names == []
        assert sat.groups == []


# ---------------------------------------------------------------------------
# TestWDKStepAnalysisConfig
# ---------------------------------------------------------------------------
class TestWDKStepAnalysisConfig:
    """Tests for WDKStepAnalysisConfig parsing."""

    def test_parse_from_camel_case(self) -> None:
        sac = WDKStepAnalysisConfig.model_validate({
            "analysisId": 100,
            "stepId": 200,
            "analysisName": "word-enrichment",
            "displayName": "Word Enrichment",
            "shortDescription": "Enriched words",
            "description": "Full description",
            "userNotes": "My analysis notes",
            "status": "COMPLETE",
            "parameters": {"pValueCutoff": "0.05"},
            "validation": {
                "level": "RUNNABLE",
                "isValid": True,
            },
        })
        assert sac.analysis_id == 100
        assert sac.step_id == 200
        assert sac.analysis_name == "word-enrichment"
        assert sac.display_name == "Word Enrichment"
        assert sac.short_description == "Enriched words"
        assert sac.description == "Full description"
        assert sac.user_notes == "My analysis notes"
        assert sac.status == "COMPLETE"
        assert sac.parameters == {"pValueCutoff": "0.05"}
        assert sac.validation is not None
        assert sac.validation.is_valid is True

    def test_defaults(self) -> None:
        sac = WDKStepAnalysisConfig.model_validate({
            "analysisId": 1,
            "stepId": 2,
            "analysisName": "go-enrichment",
        })
        assert sac.display_name == ""
        assert sac.short_description is None
        assert sac.description is None
        assert sac.user_notes is None
        assert sac.status == ""
        assert sac.parameters == {}
        assert sac.validation is None


# ---------------------------------------------------------------------------
# TestWDKUserInfo
# ---------------------------------------------------------------------------
class TestWDKUserInfo:
    """Tests for WDKUserInfo parsing."""

    def test_parse_from_camel_case(self) -> None:
        user = WDKUserInfo.model_validate({
            "id": 12345,
            "email": "researcher@example.edu",
            "isGuest": False,
            "properties": {"firstName": "Alice", "lastName": "Smith"},
        })
        assert user.id == 12345
        assert user.email == "researcher@example.edu"
        assert user.is_guest is False
        assert user.properties == {"firstName": "Alice", "lastName": "Smith"}

    def test_defaults(self) -> None:
        user = WDKUserInfo.model_validate({"id": 99})
        assert user.email is None
        assert user.is_guest is True
        assert user.properties == {}

    def test_guest_user(self) -> None:
        """GET /users/current for a guest returns isGuest=true, no email."""
        user = WDKUserInfo.model_validate({
            "id": 67890,
            "isGuest": True,
            "properties": {},
        })
        assert user.is_guest is True
        assert user.email is None


# ---------------------------------------------------------------------------
# TestWDKRecordInstance
# ---------------------------------------------------------------------------
class TestWDKRecordInstance:
    """Tests for WDKRecordInstance parsing."""

    def test_parse_from_camel_case(self) -> None:
        rec = WDKRecordInstance.model_validate({
            "displayName": "PF3D7_0100100",
            "id": [
                {"name": "source_id", "value": "PF3D7_0100100"},
                {"name": "project_id", "value": "PlasmoDB"},
            ],
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "attributes": {
                "gene_name": "VAR",
                "product": "erythrocyte membrane protein 1",
            },
            "tables": {
                "GoTerms": [
                    {"goId": "GO:0005886", "goTerm": "plasma membrane"},
                ],
            },
            "tableErrors": ["some error"],
        })
        assert rec.display_name == "PF3D7_0100100"
        assert len(rec.id) == 2
        assert rec.id[0]["name"] == "source_id"
        assert rec.record_class_name == "TranscriptRecordClasses.TranscriptRecordClass"
        assert rec.attributes["gene_name"] == "VAR"
        assert rec.tables["GoTerms"] is not None
        assert rec.table_errors == ["some error"]

    def test_defaults(self) -> None:
        rec = WDKRecordInstance.model_validate({})
        assert rec.display_name == ""
        assert rec.id == []
        assert rec.record_class_name == ""
        assert rec.attributes == {}
        assert rec.tables == {}
        assert rec.table_errors == []


# ---------------------------------------------------------------------------
# TestWDKDatasetConfig — discriminated union
# ---------------------------------------------------------------------------
class TestWDKDatasetConfig:
    """Tests for WDKDatasetConfig discriminated union (5 variants)."""

    def test_id_list_variant(self) -> None:
        adapter = TypeAdapter(WDKDatasetConfig)
        cfg = adapter.validate_python({
            "sourceType": "idList",
            "sourceContent": {"ids": ["PF3D7_0100100", "PF3D7_0831900"]},
        })
        assert isinstance(cfg, WDKDatasetConfigIdList)
        assert cfg.source_type == "idList"
        assert cfg.source_content.ids == ["PF3D7_0100100", "PF3D7_0831900"]

    def test_basket_variant(self) -> None:
        adapter = TypeAdapter(WDKDatasetConfig)
        cfg = adapter.validate_python({
            "sourceType": "basket",
            "sourceContent": {"basketName": "transcript"},
        })
        assert isinstance(cfg, WDKDatasetConfigBasket)
        assert cfg.source_content.basket_name == "transcript"

    def test_file_variant(self) -> None:
        adapter = TypeAdapter(WDKDatasetConfig)
        cfg = adapter.validate_python({
            "sourceType": "file",
            "sourceContent": {
                "temporaryFileId": "tmp-123",
                "parser": "text",
                "searchName": "GenesByLocusTag",
                "parameterName": "ds_gene_ids",
            },
        })
        assert isinstance(cfg, WDKDatasetConfigFile)
        assert cfg.source_content.temporary_file_id == "tmp-123"
        assert cfg.source_content.parser == "text"
        assert cfg.source_content.search_name == "GenesByLocusTag"

    def test_strategy_variant(self) -> None:
        adapter = TypeAdapter(WDKDatasetConfig)
        cfg = adapter.validate_python({
            "sourceType": "strategy",
            "sourceContent": {"strategyId": 42},
        })
        assert isinstance(cfg, WDKDatasetConfigStrategy)
        assert cfg.source_content.strategy_id == 42

    def test_url_variant(self) -> None:
        adapter = TypeAdapter(WDKDatasetConfig)
        cfg = adapter.validate_python({
            "sourceType": "url",
            "sourceContent": {
                "url": "https://example.com/genes.txt",
                "parser": "text",
                "searchName": "GenesByLocusTag",
                "parameterName": "ds_gene_ids",
            },
        })
        assert isinstance(cfg, WDKDatasetConfigUrl)
        assert cfg.source_content.url == "https://example.com/genes.txt"
        assert cfg.source_content.parser == "text"

    def test_invalid_discriminator_raises(self) -> None:
        adapter = TypeAdapter(WDKDatasetConfig)
        with pytest.raises(ValidationError):
            adapter.validate_python({
                "sourceType": "invalid",
                "sourceContent": {},
            })
