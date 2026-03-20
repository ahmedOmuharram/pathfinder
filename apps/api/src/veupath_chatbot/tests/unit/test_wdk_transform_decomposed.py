"""Tests for decomposed helpers extracted from build_search_doc()."""

from veupath_chatbot.integrations.vectorstore.ingest.wdk_transform import (
    SearchPayloadFields,
    _assemble_search_payload,
    _extract_canonical_params,
    _resolve_display_fields,
)


class TestExtractCanonicalParams:
    """Test _extract_canonical_params with various spec shapes."""

    def test_empty_specs(self) -> None:
        result = _extract_canonical_params([])
        assert result == []

    def test_non_dict_specs_skipped(self) -> None:
        result = _extract_canonical_params(["not-a-dict", 42, None])
        assert result == []

    def test_spec_without_name_skipped(self) -> None:
        result = _extract_canonical_params([{"type": "string"}])
        assert result == []

    def test_basic_param(self) -> None:
        specs = [
            {
                "name": "organism",
                "displayName": "Organism",
                "type": "string",
                "help": "Choose organism",
                "isRequired": True,
            }
        ]
        result = _extract_canonical_params(specs)
        assert len(result) == 1
        p = result[0]
        assert isinstance(p, dict)
        assert p["name"] == "organism"
        assert p["displayName"] == "Organism"
        assert p["type"] == "string"
        assert p["help"] == "Choose organism"
        assert p["isRequired"] is True

    def test_param_name_from_param_name_field(self) -> None:
        specs = [{"paramName": "my_param", "type": "number"}]
        result = _extract_canonical_params(specs)
        assert len(result) == 1
        assert result[0]["name"] == "my_param"

    def test_param_name_from_id(self) -> None:
        specs = [{"id": "my_id", "type": "number"}]
        result = _extract_canonical_params(specs)
        assert len(result) == 1
        assert result[0]["name"] == "my_id"

    def test_name_priority_order(self) -> None:
        """name > paramName > id for name resolution."""
        specs = [{"name": "n", "paramName": "pn", "id": "i"}]
        result = _extract_canonical_params(specs)
        assert result[0]["name"] == "n"

    def test_defaults_when_fields_missing(self) -> None:
        specs = [{"name": "x"}]
        result = _extract_canonical_params(specs)
        p = result[0]
        assert isinstance(p, dict)
        assert p["displayName"] == "x"  # falls back to name
        assert p["type"] == "string"  # defaults to string
        assert p["help"] == ""  # defaults to empty

    def test_is_required_explicit_false(self) -> None:
        specs = [{"name": "x", "isRequired": False}]
        result = _extract_canonical_params(specs)
        assert result[0]["isRequired"] is False

    def test_is_required_from_allow_empty_value(self) -> None:
        """When isRequired absent, uses allowEmptyValue to infer."""
        specs = [{"name": "x", "allowEmptyValue": False}]
        result = _extract_canonical_params(specs)
        assert result[0]["isRequired"] is True

    def test_is_required_default_when_both_absent(self) -> None:
        """When both isRequired and allowEmptyValue absent, isRequired is True (not allowEmptyValue defaults True, negated)."""
        specs = [{"name": "x"}]
        result = _extract_canonical_params(specs)
        # allowEmptyValue defaults to True in the "allowEmptyValue" not in spec path
        # so isRequired = not bool(True) would be False... but actually the code checks
        # "isRequired" not in spec -> (not bool(spec.get("allowEmptyValue", False)))
        # Since "allowEmptyValue" is also not in spec, spec.get("allowEmptyValue", False) = False
        # So isRequired = not bool(False) = True
        assert result[0]["isRequired"] is True

    def test_with_vocabulary(self) -> None:
        vocab = [["val1", "Display 1"], ["val2", "Display 2"]]
        specs = [{"name": "org", "vocabulary": vocab}]
        result = _extract_canonical_params(specs)
        p = result[0]
        assert isinstance(p, dict)
        assert p["vocabulary"] == vocab
        assert len(p["vocabularyPreview"]) == 2
        assert p["vocabularyTruncated"] is False

    def test_without_vocabulary(self) -> None:
        specs = [{"name": "x"}]
        result = _extract_canonical_params(specs)
        p = result[0]
        assert isinstance(p, dict)
        assert p["vocabulary"] is None
        assert p["vocabularyPreview"] == []
        assert p["vocabularyTruncated"] is False

    def test_default_value_from_default_value_field(self) -> None:
        specs = [{"name": "x", "defaultValue": "hello"}]
        result = _extract_canonical_params(specs)
        assert result[0]["defaultValue"] == "hello"

    def test_default_value_from_initial_display_value_field(self) -> None:
        specs = [{"name": "x", "initialDisplayValue": "fallback"}]
        result = _extract_canonical_params(specs)
        assert result[0]["defaultValue"] == "fallback"

    def test_default_value_prefers_default_value_field(self) -> None:
        specs = [
            {"name": "x", "defaultValue": "primary", "initialDisplayValue": "fallback"}
        ]
        result = _extract_canonical_params(specs)
        assert result[0]["defaultValue"] == "primary"

    def test_multiple_specs(self) -> None:
        specs = [
            {"name": "a", "type": "string"},
            {"name": "b", "type": "number"},
            {"name": "c", "type": "enum"},
        ]
        result = _extract_canonical_params(specs)
        assert len(result) == 3
        names = [p["name"] for p in result]
        assert names == ["a", "b", "c"]

    def test_allow_empty_value_explicit(self) -> None:
        specs = [{"name": "x", "allowEmptyValue": True}]
        result = _extract_canonical_params(specs)
        assert result[0]["allowEmptyValue"] is True

    def test_allow_empty_value_absent(self) -> None:
        specs = [{"name": "x"}]
        result = _extract_canonical_params(specs)
        assert result[0]["allowEmptyValue"] is None


class TestResolveDisplayFields:
    """Test _resolve_display_fields with various field combinations."""

    def test_all_from_details(self) -> None:
        details = {
            "displayName": "Gene Search",
            "shortDisplayName": "GS",
            "description": "Search for genes",
            "summary": "Gene summary",
            "help": "Help text here",
        }
        display_name, short, desc, summary, help_text = _resolve_display_fields(
            details, {}, "GenesByText"
        )
        assert display_name == "Gene Search"
        assert short == "GS"
        assert desc == "Search for genes"
        assert summary == "Gene summary"
        assert help_text == "Help text here"

    def test_fallback_to_summary(self) -> None:
        details = {}
        summary_obj = {
            "displayName": "From Summary",
            "shortDisplayName": "FS",
            "description": "Summary desc",
        }
        display_name, short, desc, summary, help_text = _resolve_display_fields(
            details, summary_obj, "SomeName"
        )
        assert display_name == "From Summary"
        assert short == "FS"
        assert desc == "Summary desc"
        assert summary == ""
        assert help_text == ""

    def test_fallback_to_search_name(self) -> None:
        display_name, short, desc, summary, help_text = _resolve_display_fields(
            {}, {}, "MySearchName"
        )
        assert display_name == "MySearchName"
        assert short == ""
        assert desc == ""
        assert summary == ""
        assert help_text == ""

    def test_details_overrides_summary(self) -> None:
        details = {"displayName": "Details Display"}
        summary_obj = {"displayName": "Summary Display"}
        display_name, _, _, _, _ = _resolve_display_fields(details, summary_obj, "Name")
        assert display_name == "Details Display"

    def test_none_values_coerced_to_str(self) -> None:
        details = {"displayName": None, "summary": None}
        display_name, _short, _desc, summary, _help_text = _resolve_display_fields(
            details, {}, "FallbackName"
        )
        # None displayName should fall through to search_name
        assert display_name == "FallbackName"
        assert summary == ""

    def test_integer_values_coerced(self) -> None:
        details = {"displayName": 42}
        display_name, _, _, _, _ = _resolve_display_fields(details, {}, "Name")
        assert display_name == "42"


class TestAssembleSearchPayload:
    """Test _assemble_search_payload builds correct structure."""

    def _default_fields(self) -> SearchPayloadFields:
        return SearchPayloadFields(
            site_id="plasmodb",
            rt_name="transcript",
            search_name="GenesByText",
            display_name="Text Search",
            short="TS",
            description="Search by text",
            summary="Summary text",
            help_text="Help here",
            canonical_params=[],
            details_unwrapped={},
            summary_unwrapped={},
            base_url="https://plasmodb.org/plasmodb/service",
            is_internal=False,
            details_error=None,
        )

    def test_basic_structure(self) -> None:
        args = self._default_fields()
        payload = _assemble_search_payload(args)
        assert payload["siteId"] == "plasmodb"
        assert payload["recordType"] == "transcript"
        assert payload["searchName"] == "GenesByText"
        assert payload["displayName"] == "Text Search"
        assert payload["shortDisplayName"] == "TS"
        assert payload["description"] == "Search by text"
        assert payload["summary"] == "Summary text"
        assert payload["help"] == "Help here"
        assert payload["isInternal"] is False
        assert payload["paramSpecs"] == []

    def test_source_url(self) -> None:
        args = self._default_fields()
        payload = _assemble_search_payload(args)
        expected = "https://plasmodb.org/plasmodb/service/record-types/transcript/searches/GenesByText"
        assert payload["sourceUrl"] == expected

    def test_ingested_at_is_int(self) -> None:
        args = self._default_fields()
        payload = _assemble_search_payload(args)
        assert isinstance(payload["ingestedAt"], int)

    def test_source_hash_present(self) -> None:
        args = self._default_fields()
        payload = _assemble_search_payload(args)
        assert "sourceHash" in payload
        assert isinstance(payload["sourceHash"], str)

    def test_details_error_included(self) -> None:
        args = self._default_fields()
        args.details_error = "connection timeout"
        payload = _assemble_search_payload(args)
        assert payload["detailsError"] == "connection timeout"

    def test_no_details_error_no_key(self) -> None:
        args = self._default_fields()
        payload = _assemble_search_payload(args)
        assert "detailsError" not in payload

    def test_fields_from_details(self) -> None:
        args = self._default_fields()
        args.details_unwrapped = {
            "fullName": "full.name.here",
            "urlSegment": "GenesByText",
            "outputRecordClassName": "GeneRecordClasses.GeneRecordClass",
            "paramNames": ["a", "b"],
            "groups": [{"name": "g1"}],
            "isAnalyzable": True,
            "isCacheable": True,
            "isBeta": False,
            "queryName": "GenesByTextQuery",
            "newBuild": "64",
            "reviseBuild": "65",
        }
        payload = _assemble_search_payload(args)
        assert payload["fullName"] == "full.name.here"
        assert payload["urlSegment"] == "GenesByText"
        assert payload["outputRecordClassName"] == "GeneRecordClasses.GeneRecordClass"
        assert payload["paramNames"] == ["a", "b"]
        assert payload["isAnalyzable"] is True
        assert payload["isBeta"] is False
        assert payload["queryName"] == "GenesByTextQuery"

    def test_fields_fallback_to_summary(self) -> None:
        args = self._default_fields()
        args.details_unwrapped = {}
        args.summary_unwrapped = {
            "fullName": "summary.full",
            "urlSegment": "summarySegment",
            "paramNames": ["c"],
        }
        payload = _assemble_search_payload(args)
        assert payload["fullName"] == "summary.full"
        assert payload["urlSegment"] == "summarySegment"
        assert payload["paramNames"] == ["c"]

    def test_output_record_class_name_defaults_to_rt(self) -> None:
        args = self._default_fields()
        payload = _assemble_search_payload(args)
        assert payload["outputRecordClassName"] == "transcript"

    def test_url_segment_defaults_to_search_name(self) -> None:
        args = self._default_fields()
        payload = _assemble_search_payload(args)
        assert payload["urlSegment"] == "GenesByText"
