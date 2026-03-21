"""Tests verifying WDK mock fixtures match the REAL VEuPathDB WDK API.

These shapes were confirmed by CURLing live PlasmoDB endpoints on 2026-03-06.
If a fixture's shape drifts from the real API, these tests will catch it before
the mismatch reaches production.

Run::

    pytest src/veupath_chatbot/tests/unit/test_wdk_fixture_shapes.py -v
"""

import inspect

from veupath_chatbot.integrations.veupathdb.temporary_results import (
    TemporaryResultsAPI,
)
from veupath_chatbot.tests.fixtures.wdk_responses import (
    record_types_expanded_response,
    record_types_response,
    search_details_response,
    searches_response,
    standard_report_response,
    step_get_response,
    strategy_get_response,
    strategy_list_item,
    strategy_list_response,
    user_current_response,
)


# ---------------------------------------------------------------------------
# /record-types  (non-expanded)
# ---------------------------------------------------------------------------
class TestRecordTypesShape:
    """GET /record-types returns a flat list of strings (non-expanded)."""

    def test_is_list_of_strings(self) -> None:
        data = record_types_response()
        assert isinstance(data, list)
        for item in data:
            assert isinstance(item, str), (
                f"Non-expanded record-types must be plain strings, got {type(item)}"
            )

    def test_includes_transcript_and_gene(self) -> None:
        data = record_types_response()
        assert "transcript" in data
        assert "gene" in data


class TestRecordTypesExpandedShape:
    """GET /record-types?format=expanded returns objects with urlSegment."""

    def test_is_list_of_dicts(self) -> None:
        data = record_types_expanded_response()
        assert isinstance(data, list)
        for item in data:
            assert isinstance(item, dict)

    def test_has_required_keys(self) -> None:
        """Real expanded record type has urlSegment, fullName, displayName."""
        for item in record_types_expanded_response():
            assert "urlSegment" in item
            assert "fullName" in item
            assert "displayName" in item
            assert "hasAllRecordsQuery" in item
            assert "primaryKeyColumnRefs" in item

    def test_no_iconname_field(self) -> None:
        """The real WDK does NOT have an 'iconName' field on record types."""
        for item in record_types_expanded_response():
            assert "iconName" not in item

    def test_no_name_field(self) -> None:
        """The real WDK uses 'fullName' not 'name' on expanded record types."""
        for item in record_types_expanded_response():
            assert "name" not in item


# ---------------------------------------------------------------------------
# /record-types/{type}/searches
# ---------------------------------------------------------------------------
class TestSearchesListShape:
    """GET /record-types/transcript/searches returns search list items."""

    def test_no_isinternal_field(self) -> None:
        """The real search list NEVER includes 'isInternal'.
        Internal searches are identified by fullName starting with
        'InternalQuestions.' instead.
        """
        for search in searches_response():
            assert "isInternal" not in search

    def test_no_name_field(self) -> None:
        """The real search list uses 'fullName' and 'queryName', not 'name'."""
        for search in searches_response():
            assert "name" not in search

    def test_has_required_fields(self) -> None:
        """Each search item has the fields observed in the real API."""
        required = {
            "urlSegment",
            "fullName",
            "queryName",
            "displayName",
            "shortDisplayName",
            "outputRecordClassName",
            "paramNames",
            "isAnalyzable",
            "isCacheable",
        }
        for search in searches_response():
            missing = required - set(search.keys())
            assert not missing, (
                f"Search '{search.get('urlSegment')}' missing keys: {missing}"
            )

    def test_boolean_search_uses_underscores(self) -> None:
        """Boolean question urlSegment uses underscores, not dots.
        Real PlasmoDB: boolean_question_TranscriptRecordClasses_TranscriptRecordClass
        """
        for search in searches_response():
            url = search.get("urlSegment", "")
            if "boolean_question" in url:
                assert "." not in url, (
                    f"Boolean urlSegment must use underscores not dots: {url}"
                )
                # Param names should also use underscores
                for pname in search.get("paramNames", []):
                    if pname.startswith("bq_"):
                        assert "." not in pname, (
                            f"Boolean param name must use underscores: {pname}"
                        )

    def test_description_not_always_present(self) -> None:
        """'description' is present on some searches (transforms) but not all."""
        has_desc = [s for s in searches_response() if "description" in s]
        no_desc = [s for s in searches_response() if "description" not in s]
        # At least one search should lack description (like AllGenes, boolean, etc)
        assert len(no_desc) > 0
        # At least one should have it (like transforms)
        assert len(has_desc) > 0


# ---------------------------------------------------------------------------
# /record-types/{type}/searches/{name}?expandParams=true
# ---------------------------------------------------------------------------
class TestSearchDetailsShape:
    """GET search details wraps content in {searchData, validation}."""

    def test_top_level_has_searchdata_and_validation(self) -> None:
        """Real API returns exactly {searchData: {...}, validation: {...}}."""
        for name in ["GenesByTaxon", "GenesByTextSearch", "GenesByOrthologs"]:
            details = search_details_response(name)
            assert "searchData" in details, f"Missing searchData for {name}"
            assert "validation" in details, f"Missing validation for {name}"

    def test_no_top_level_urlsegment_or_name(self) -> None:
        """urlSegment, name, etc. are inside searchData, NOT at top level."""
        for name in ["GenesByTaxon", "GenesByTextSearch"]:
            details = search_details_response(name)
            assert "urlSegment" not in details
            assert "name" not in details
            assert "outputRecordClassName" not in details

    def test_urlsegment_inside_searchdata(self) -> None:
        details = search_details_response("GenesByTaxon")
        assert details["searchData"]["urlSegment"] == "GenesByTaxon"

    def test_validation_shape(self) -> None:
        """Validation has 'level' and 'isValid' fields."""
        details = search_details_response("GenesByTaxon")
        validation = details["validation"]
        assert "level" in validation
        assert "isValid" in validation

    def test_no_default_param_values_key(self) -> None:
        """Real WDK does NOT have 'defaultParamValues' on searchData.
        Instead, each parameter has 'initialDisplayValue'.
        """
        for name in ["GenesByTaxon", "GenesByTextSearch", "GenesByOrthologs"]:
            sd = search_details_response(name)["searchData"]
            assert "defaultParamValues" not in sd

    def test_params_have_initial_display_value(self) -> None:
        """Each parameter has 'initialDisplayValue' for its default."""
        for name in ["GenesByTaxon", "GenesByTextSearch", "GenesByOrthologs"]:
            sd = search_details_response(name)["searchData"]
            for param in sd["parameters"]:
                assert "initialDisplayValue" in param, (
                    f"Param '{param['name']}' in search '{name}' "
                    f"missing 'initialDisplayValue'"
                )

    def test_vocabulary_entries_are_three_element_arrays(self) -> None:
        """Flat vocabulary entries are [term, display, parent] (3 elements).
        Tree vocabularies use {data: {term, display}, children: [...]}.
        """
        details = search_details_response("GenesByTextSearch")
        for param in details["searchData"]["parameters"]:
            vocab = param.get("vocabulary")
            if vocab is None:
                continue
            if isinstance(vocab, list):
                for entry in vocab:
                    assert isinstance(entry, list), (
                        f"Flat vocab entry should be a list, got {type(entry)}"
                    )
                    assert len(entry) == 3, (
                        f"Vocab entry should be [term, display, parent], "
                        f"got {len(entry)} elements: {entry}"
                    )
            elif isinstance(vocab, dict):
                # Tree vocabulary
                assert "data" in vocab
                assert "children" in vocab
                assert "term" in vocab["data"]
                assert "display" in vocab["data"]

    def test_boolean_operator_vocab_entries(self) -> None:
        """Boolean operator vocabulary has the real WDK operator values."""
        boolean_name = "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"
        details = search_details_response(boolean_name)
        sd = details["searchData"]
        op_param = None
        for p in sd["parameters"]:
            if p["name"] == "bq_operator":
                op_param = p
                break
        assert op_param is not None

        vocab = op_param["vocabulary"]
        terms = [v[0] for v in vocab]
        assert "UNION" in terms
        assert "INTERSECT" in terms
        assert "MINUS" in terms
        assert "RMINUS" in terms
        assert "LONLY" in terms
        assert "RONLY" in terms


# ---------------------------------------------------------------------------
# Standard report response
# ---------------------------------------------------------------------------
class TestStandardReportShape:
    """POST .../reports/standard returns {records, meta}."""

    def test_has_records_and_meta(self) -> None:
        data = standard_report_response()
        assert "records" in data
        assert "meta" in data

    def test_meta_has_total_count(self) -> None:
        data = standard_report_response()
        meta = data["meta"]
        assert "totalCount" in meta
        assert isinstance(meta["totalCount"], int)

    def test_record_id_is_multi_part(self) -> None:
        """Real transcript records have 3-part primary keys."""
        data = standard_report_response()
        for record in data["records"]:
            pk = record["id"]
            assert isinstance(pk, list)
            assert len(pk) == 3, (
                f"Transcript record should have 3-part primary key, got {len(pk)}"
            )
            names = [part["name"] for part in pk]
            assert "gene_source_id" in names
            assert "source_id" in names
            assert "project_id" in names

    def test_record_has_expected_fields(self) -> None:
        data = standard_report_response()
        for record in data["records"]:
            assert "displayName" in record
            assert "recordClassName" in record
            assert "attributes" in record
            assert "tables" in record
            assert "tableErrors" in record

    def test_record_class_is_transcript(self) -> None:
        """PlasmoDB gene searches use the transcript record class."""
        data = standard_report_response()
        for record in data["records"]:
            assert record["recordClassName"] == (
                "TranscriptRecordClasses.TranscriptRecordClass"
            )


# ---------------------------------------------------------------------------
# Strategy GET response (detail)
# ---------------------------------------------------------------------------
class TestStrategyGetShape:
    """GET /users/{id}/strategies/{id} shape."""

    def test_has_required_fields(self) -> None:
        data = strategy_get_response()
        required = {
            "strategyId",
            "name",
            "isSaved",
            "isPublic",
            "isDeleted",
            "isValid",
            "rootStepId",
            "estimatedSize",
            "recordClassName",
            "stepTree",
            "signature",
            "lastModified",
            "author",
            "releaseVersion",
            "isExample",
            "leafAndTransformStepCount",
            "nameOfFirstStep",
            "lastViewed",
        }
        missing = required - set(data.keys())
        assert not missing, f"Strategy response missing keys: {missing}"

    def test_has_steps_dict(self) -> None:
        """The real WDK detail response DOES include a 'steps' dict.
        Steps are keyed by step ID string with full step detail objects."""
        data = strategy_get_response()
        assert "steps" in data
        steps = data["steps"]
        assert isinstance(steps, dict)
        for key, value in steps.items():
            assert isinstance(key, str)  # Step IDs are string keys
            assert isinstance(value, dict)
            assert "searchName" in value
            assert "searchConfig" in value

    def test_step_tree_structure(self) -> None:
        """stepTree is a recursive {stepId, primaryInput?, secondaryInput?}."""
        data = strategy_get_response()
        tree = data["stepTree"]
        assert "stepId" in tree
        assert isinstance(tree["stepId"], int)
        # With default 3 steps, root has primaryInput
        if "primaryInput" in tree:
            assert "stepId" in tree["primaryInput"]

    def test_description_is_empty_string(self) -> None:
        """WDK uses empty string for description, not null."""
        data = strategy_get_response()
        assert data["description"] == ""

    def test_last_modified_key_name(self) -> None:
        """WDK uses 'lastModified', not 'lastModifiedTime'."""
        data = strategy_get_response()
        assert "lastModified" in data
        assert "lastModifiedTime" not in data

    def test_steps_match_step_tree(self) -> None:
        """Steps dict keys should correspond to step IDs in the tree."""
        data = strategy_get_response()
        steps = data["steps"]
        # Collect all step IDs from the tree
        tree_ids: set[int] = set()

        def _collect(node: dict) -> None:
            tree_ids.add(node["stepId"])
            if "primaryInput" in node:
                _collect(node["primaryInput"])
            if "secondaryInput" in node:
                _collect(node["secondaryInput"])

        _collect(data["stepTree"])
        assert tree_ids == {int(k) for k in steps}

    def test_step_objects_have_required_fields(self) -> None:
        """Each step in the steps dict has core fields."""
        data = strategy_get_response()
        required = {
            "id",
            "searchName",
            "searchConfig",
            "estimatedSize",
            "recordClassName",
        }
        for key, step in data["steps"].items():
            missing = required - set(step.keys())
            assert not missing, f"Step '{key}' missing keys: {missing}"


# ---------------------------------------------------------------------------
# Strategy list item (summary — no stepTree/steps)
# ---------------------------------------------------------------------------
class TestStrategyListItemShape:
    """GET /users/{id}/strategies list items are summaries."""

    def test_has_required_fields(self) -> None:
        data = strategy_list_item()
        required = {
            "strategyId",
            "name",
            "description",
            "author",
            "rootStepId",
            "recordClassName",
            "signature",
            "createdTime",
            "lastModified",
            "lastViewed",
            "releaseVersion",
            "isPublic",
            "isSaved",
            "isValid",
            "isDeleted",
            "isExample",
            "organization",
            "estimatedSize",
            "nameOfFirstStep",
            "leafAndTransformStepCount",
        }
        missing = required - set(data.keys())
        assert not missing, f"Strategy list item missing keys: {missing}"

    def test_no_step_tree(self) -> None:
        """List items do NOT include stepTree (detail-only)."""
        data = strategy_list_item()
        assert "stepTree" not in data

    def test_no_steps_dict(self) -> None:
        """List items do NOT include steps dict (detail-only)."""
        data = strategy_list_item()
        assert "steps" not in data

    def test_field_types(self) -> None:
        """Verify correct types for key fields."""
        data = strategy_list_item()
        assert isinstance(data["strategyId"], int)
        assert isinstance(data["name"], str)
        assert isinstance(data["description"], str)
        assert isinstance(data["author"], str)
        assert isinstance(data["rootStepId"], int)
        assert isinstance(data["isPublic"], bool)
        assert isinstance(data["isSaved"], bool)
        assert isinstance(data["isValid"], bool)
        assert isinstance(data["isDeleted"], bool)
        assert isinstance(data["isExample"], bool)
        assert isinstance(data["estimatedSize"], int)
        assert isinstance(data["leafAndTransformStepCount"], int)
        assert isinstance(data["releaseVersion"], str)
        assert isinstance(data["signature"], str)

    def test_list_response_returns_list(self) -> None:
        data = strategy_list_response(count=3)
        assert isinstance(data, list)
        assert len(data) == 3
        for item in data:
            assert isinstance(item, dict)
            assert "strategyId" in item
            assert "stepTree" not in item
            assert "steps" not in item

    def test_list_response_unique_ids(self) -> None:
        data = strategy_list_response(count=5)
        ids = [item["strategyId"] for item in data]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Step GET response (separate from strategy)
# ---------------------------------------------------------------------------
class TestStepGetShape:
    """GET /users/{id}/steps/{stepId} shape."""

    def test_has_required_fields(self) -> None:
        data = step_get_response()
        required = {
            "id",
            "searchName",
            "searchConfig",
            "estimatedSize",
            "recordClassName",
        }
        missing = required - set(data.keys())
        assert not missing, f"Step response missing keys: {missing}"

    def test_search_config_has_parameters(self) -> None:
        data = step_get_response()
        assert "parameters" in data["searchConfig"]


# ---------------------------------------------------------------------------
# User current response
# ---------------------------------------------------------------------------
class TestUserCurrentShape:
    def test_has_id(self) -> None:
        data = user_current_response()
        assert "id" in data
        assert isinstance(data["id"], int)

    def test_has_is_guest(self) -> None:
        data = user_current_response()
        assert "isGuest" in data


# ---------------------------------------------------------------------------
# Temporary results
# ---------------------------------------------------------------------------
class TestTemporaryResultsContract:
    """POST /temporary-results shape verification."""

    def test_create_uses_report_name_not_reporter_name(self) -> None:
        """WDK expects 'reportName', not 'reporterName'.

        Using 'reporterName' triggers:
          400: JSONObject["reportName"] not found.

        Confirmed by CURL on 2026-03-06.
        """
        source = inspect.getsource(TemporaryResultsAPI.create_temporary_result)
        # The payload dict must use "reportName" as the key
        assert '"reportName"' in source
        # The payload dict must NOT use "reporterName" as a key
        # (comments mentioning it are fine, so check assignment context)
        assert 'payload["reporterName"]' not in source
        assert "'reporterName'" not in source

    def test_create_uses_step_id_field(self) -> None:
        """WDK temporary-results creation requires 'stepId' or
        'searchName'+'searchConfig', not both.
        """
        source = inspect.getsource(TemporaryResultsAPI.create_temporary_result)
        assert '"stepId"' in source
