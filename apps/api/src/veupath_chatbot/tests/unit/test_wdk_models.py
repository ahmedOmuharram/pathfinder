"""Unit tests for WDK structural response models.

Verifies fixture shapes match real WDK API, application-specific logic
(default choices, discriminated unions, spec models), and field naming
that reflects our WDK alignment decisions.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKAnswer,
    WDKAttributeField,
    WDKColumnDistribution,
    WDKDatasetConfig,
    WDKDatasetConfigBasket,
    WDKDatasetConfigFile,
    WDKDatasetConfigIdList,
    WDKDatasetConfigStrategy,
    WDKDatasetConfigUrl,
    WDKIdentifier,
    WDKRecordType,
    WDKReporter,
    WDKSearch,
    WDKSearchConfig,
    WDKSearchResponse,
    WDKStep,
    WDKStepAnalysisConfig,
    WDKStepTree,
    WDKStrategyDetails,
    WDKStrategySummary,
    WDKValidation,
)
from veupath_chatbot.tests.fixtures.wdk_responses import (
    search_details_response,
    wdk_record_type_json,
    wdk_step_json,
    wdk_strategy_details_json,
    wdk_strategy_summary_json,
)


# ---------------------------------------------------------------------------
# TestWDKSearchConfig
# ---------------------------------------------------------------------------
class TestWDKSearchConfig:
    """Tests for WDKSearchConfig — kept: view_filters field (our addition)."""

    def test_parse_with_view_filters(self) -> None:
        cfg = WDKSearchConfig.model_validate(
            {
                "parameters": {},
                "viewFilters": [{"name": "gene_boolean_filter", "value": True}],
            },
        )
        assert len(cfg.view_filters) == 1
        assert cfg.view_filters[0].name == "gene_boolean_filter"


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


# ---------------------------------------------------------------------------
# TestWDKStep
# ---------------------------------------------------------------------------
class TestWDKStep:
    """Tests for WDKStep parsing from realistic WDK JSON."""

    def test_parse_from_fixture(self) -> None:
        step = WDKStep.model_validate(wdk_step_json())
        assert step.id == 12345
        assert step.search_name == "GenesByTaxon"


# ---------------------------------------------------------------------------
# TestWDKStrategySummary
# ---------------------------------------------------------------------------
class TestWDKStrategySummary:
    """Tests for WDKStrategySummary parsing."""

    def test_estimated_size_as_number(self) -> None:
        summary = WDKStrategySummary.model_validate(
            wdk_strategy_summary_json(),
        )
        assert summary.estimated_size == 150


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

    def test_param_names_always_present(self) -> None:
        data = {
            "urlSegment": "GenesByTaxon",
            "paramNames": ["organism"],
        }
        search = WDKSearch.model_validate(data)
        assert isinstance(search.param_names, list)
        assert "organism" in search.param_names


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

    def test_url_segment_is_canonical(self) -> None:
        rt = WDKRecordType.model_validate(wdk_record_type_json())
        assert rt.url_segment == "transcript"


# ---------------------------------------------------------------------------
# TestWDKIdentifier
# ---------------------------------------------------------------------------
class TestWDKIdentifier:
    """Tests for WDKIdentifier (replaces WDKStrategyCreateResponse)."""

    def test_same_shape_as_strategy_create_response(self) -> None:
        """WDKIdentifier has the same shape as the old WDKStrategyCreateResponse."""
        ident = WDKIdentifier.model_validate({"id": 99999})
        assert ident.id == 99999


# ---------------------------------------------------------------------------
# TestWDKStepAnalysisConfigStatus
# ---------------------------------------------------------------------------
class TestWDKStepAnalysisConfigStatus:
    """Tests for WDKStepAnalysisConfig.status typed as WDKAnalysisStatus."""

    def test_status_from_wdk_response(self) -> None:
        raw = {
            "analysisId": 1,
            "stepId": 2,
            "analysisName": "go-enrichment",
            "status": "COMPLETE",
        }
        cfg = WDKStepAnalysisConfig.model_validate(raw)
        assert cfg.status == "COMPLETE"


# ---------------------------------------------------------------------------
# TestWDKColumnDistribution
# ---------------------------------------------------------------------------
class TestWDKColumnDistribution:
    """Tests for WDKColumnDistribution parsing."""

    def test_parse_string_distribution(self) -> None:
        raw = {
            "histogram": [
                {"value": 2890, "binStart": "Pf3D7", "binEnd": "Pf3D7", "binLabel": "Pf3D7"},
            ],
            "statistics": {"subsetSize": 4429, "numVarValues": 4429, "numDistinctValues": 1},
        }
        dist = WDKColumnDistribution.model_validate(raw)
        assert len(dist.histogram) == 1
        assert dist.histogram[0].value == 2890
        assert dist.histogram[0].bin_start == "Pf3D7"
        assert dist.statistics.subset_size == 4429
        assert dist.statistics.num_distinct_values == 1





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


# ---------------------------------------------------------------------------
# TestPatchStepSpec — mutable request model
# ---------------------------------------------------------------------------
class TestPatchStepSpec:
    """Tests for PatchStepSpec (mutable request model for step updates)."""

    def test_custom_name(self) -> None:
        spec = PatchStepSpec(custom_name="My Step")
        assert spec.custom_name == "My Step"

    def test_not_frozen(self) -> None:
        spec = PatchStepSpec()
        spec.custom_name = "Updated"
        assert spec.custom_name == "Updated"


# ---------------------------------------------------------------------------
# TestNewStepSpec — mutable request model (extends PatchStepSpec)
# ---------------------------------------------------------------------------
class TestNewStepSpec:
    """Tests for NewStepSpec (mutable request model for step creation)."""

    def test_requires_search_name_and_config(self) -> None:
        spec = NewStepSpec(
            search_name="GenesByText",
            search_config=WDKSearchConfig(parameters={"text_expression": "kinase"}),
        )
        assert spec.search_name == "GenesByText"
        assert spec.search_config.parameters == {"text_expression": "kinase"}

    def test_inherits_patch_fields(self) -> None:
        spec = NewStepSpec(
            search_name="GenesByText",
            search_config=WDKSearchConfig(parameters={}),
            custom_name="My Search",
        )
        assert spec.custom_name == "My Search"

    def test_wdk_weight_in_search_config(self) -> None:
        spec = NewStepSpec(
            search_name="GenesByText",
            search_config=WDKSearchConfig(parameters={}, wdk_weight=5),
        )
        assert spec.search_config.wdk_weight == 5


# ---------------------------------------------------------------------------
# TestWDKAttributeField
# ---------------------------------------------------------------------------
class TestWDKAttributeField:
    """Tests for WDKAttributeField and WDKReporter models."""

    def test_parse_reporter(self) -> None:
        reporter = WDKReporter.model_validate({
            "name": "attributesTabular",
            "type": "standard",
            "displayName": "Tab/CSV",
            "description": "Tab-delimited",
            "isInReport": True,
            "scopes": ["results"],
        })
        assert reporter.name == "attributesTabular"
        assert reporter.is_in_report is True
        assert reporter.scopes == ["results"]

    def test_parse_attribute_field_full(self) -> None:
        field = WDKAttributeField.model_validate({
            "name": "gene_source_id",
            "displayName": "Gene ID",
            "help": "Unique identifier",
            "type": "string",
            "isSortable": True,
            "isRemovable": True,
            "isDisplayable": True,
            "isInReport": True,
            "truncateTo": 100,
            "formats": [{"name": "text", "type": "standard", "displayName": "Text", "isInReport": True, "scopes": []}],
            "properties": {"datatype": ["string"]},
        })
        assert field.name == "gene_source_id"
        assert field.display_name == "Gene ID"
        assert field.is_sortable is True
        assert field.is_in_report is True
        assert len(field.formats) == 1
        assert field.formats[0].name == "text"



# ---------------------------------------------------------------------------
# TestWDKRecordTypeAttributes
# ---------------------------------------------------------------------------
class TestWDKRecordTypeAttributes:
    """Tests for typed attribute fields on WDKRecordType."""

    def test_parse_attributes_as_list(self) -> None:
        rt = WDKRecordType.model_validate({
            "urlSegment": "transcript",
            "attributes": [
                {"name": "gene_source_id", "displayName": "Gene ID", "type": "string", "isSortable": True},
                {"name": "organism", "displayName": "Organism", "type": "string"},
            ],
        })
        assert rt.attributes is not None
        assert len(rt.attributes) == 2
        assert rt.attributes[0].name == "gene_source_id"
        assert rt.attributes[0].is_sortable is True

    def test_parse_attributes_map_as_dict(self) -> None:
        rt = WDKRecordType.model_validate({
            "urlSegment": "transcript",
            "attributesMap": {
                "gene_source_id": {"name": "gene_source_id", "displayName": "Gene ID", "type": "string"},
                "organism": {"name": "organism", "displayName": "Organism"},
            },
        })
        assert rt.attributes_map is not None
        assert len(rt.attributes_map) == 2
        assert rt.attributes_map["gene_source_id"].display_name == "Gene ID"



# ---------------------------------------------------------------------------
# TestWDKAnswerTypedRecords
# ---------------------------------------------------------------------------
class TestWDKAnswerTypedRecords:
    """Tests for WDKAnswer.records typed record parsing."""

    def test_parse_answer_with_typed_records(self) -> None:
        answer = WDKAnswer.model_validate({
            "meta": {"totalCount": 2, "responseCount": 2},
            "records": [
                {
                    "displayName": "PF3D7_0100100",
                    "id": [{"name": "source_id", "value": "PF3D7_0100100"}],
                    "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
                    "attributes": {"gene_source_id": "PF3D7_0100100", "organism": "P. falciparum"},
                    "tables": {},
                    "tableErrors": [],
                },
                {
                    "displayName": "PF3D7_0200200",
                    "id": [{"name": "source_id", "value": "PF3D7_0200200"}],
                    "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
                    "attributes": {"gene_source_id": "PF3D7_0200200"},
                    "tables": {},
                    "tableErrors": [],
                },
            ],
        })
        assert len(answer.records) == 2
        assert answer.records[0].id == [{"name": "source_id", "value": "PF3D7_0100100"}]
        assert answer.records[0].attributes["gene_source_id"] == "PF3D7_0100100"
        assert answer.records[0].display_name == "PF3D7_0100100"
        assert answer.records[1].id == [{"name": "source_id", "value": "PF3D7_0200200"}]

