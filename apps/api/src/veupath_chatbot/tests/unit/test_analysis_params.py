"""Tests for WDK analysis parameter merging.

Verifies that ``extract_default_params`` handles the real WDK response
structure — parameters nested under ``searchData`` with default values
in ``initialDisplayValue`` (not ``defaultValue``) — and that
``merge_analysis_params`` always merges defaults with user parameters.

WDK source: ``ParamFormatter.java`` uses ``JsonKeys.INITIAL_DISPLAY_VALUE``
for the parameter's stable default/initial value.

WDK ``EnumParamFormatter.getParamType()`` emits JSON type strings:
  - ``"single-pick-vocabulary"`` for single-pick enum/vocab params
  - ``"multi-pick-vocabulary"`` for multi-pick enum/vocab params
All vocab param values must be JSON-encoded arrays per
``AbstractEnumParam.convertToTerms()`` → ``new JSONArray(stableValue)``.
"""

from veupath_chatbot.services.enrichment.params import extract_default_params
from veupath_chatbot.services.wdk.helpers import merge_analysis_params

# ---------------------------------------------------------------------------
# Real WDK response structure (from the go-enrichment analysis type endpoint)
# uses "initialDisplayValue" (from ParamFormatter.java), NOT "defaultValue".
# Type strings come from EnumParamFormatter.getParamType().
# ---------------------------------------------------------------------------

_GO_ENRICHMENT_FORM_META = {
    "searchData": {
        "paramNames": [
            "organism",
            "goAssociationsOntologies",
            "goEvidenceCodes",
            "goSubset",
            "pValueCutoff",
        ],
        "name": "go-enrichment",
        "displayName": "Gene Ontology Enrichment",
        "parameters": [
            {
                "name": "organism",
                "displayName": "Organism",
                "initialDisplayValue": "Plasmodium falciparum 3D7",
                "type": "single-pick-vocabulary",
            },
            {
                "name": "goAssociationsOntologies",
                "displayName": "GO Association Ontologies",
                "initialDisplayValue": "Biological Process",
                "type": "single-pick-vocabulary",
            },
            {
                "name": "goEvidenceCodes",
                "displayName": "Evidence Codes",
                "initialDisplayValue": "all",
                "type": "single-pick-vocabulary",
            },
            {
                "name": "goSubset",
                "displayName": "GO Subset",
                "initialDisplayValue": "No",
                "type": "single-pick-vocabulary",
            },
            {
                "name": "pValueCutoff",
                "displayName": "P-Value Cutoff",
                "initialDisplayValue": "0.05",
                "type": "number",
            },
        ],
    },
    "validation": {"level": "RUNNABLE", "isValid": True},
}

_PATHWAY_FORM_META = {
    "searchData": {
        "paramNames": [
            "organism",
            "pathwaysSources",
            "pValueCutoff",
            "exact_match_only",
            "exclude_incomplete_ec",
        ],
        "name": "pathway-enrichment",
        "parameters": [
            {
                "name": "organism",
                "initialDisplayValue": "Plasmodium falciparum 3D7",
                "type": "single-pick-vocabulary",
            },
            {
                "name": "pathwaysSources",
                "initialDisplayValue": "KEGG",
                "type": "single-pick-vocabulary",
            },
            {
                "name": "pValueCutoff",
                "initialDisplayValue": "0.05",
                "type": "number",
            },
            {
                "name": "exact_match_only",
                "initialDisplayValue": "No",
                "type": "single-pick-vocabulary",
            },
            {
                "name": "exclude_incomplete_ec",
                "initialDisplayValue": "Yes",
                "type": "single-pick-vocabulary",
            },
        ],
    },
    "validation": {"level": "RUNNABLE", "isValid": True},
}


class TestExtractDefaultParamsWdkFormat:
    """extract_default_params must handle real WDK nested structure."""

    def test_extracts_from_search_data_with_initial_display_value(self) -> None:
        """WDK uses initialDisplayValue (not defaultValue) for defaults.

        Vocab params (single-pick-vocabulary) are encoded as JSON arrays
        per AbstractEnumParam.convertToTerms().
        """
        result = extract_default_params(_GO_ENRICHMENT_FORM_META)
        assert result == {
            "organism": '["Plasmodium falciparum 3D7"]',
            "goAssociationsOntologies": '["Biological Process"]',
            "goEvidenceCodes": '["all"]',
            "goSubset": '["No"]',
            "pValueCutoff": "0.05",
        }

    def test_extracts_pathway_defaults(self) -> None:
        result = extract_default_params(_PATHWAY_FORM_META)
        assert result == {
            "organism": '["Plasmodium falciparum 3D7"]',
            "pathwaysSources": '["KEGG"]',
            "pValueCutoff": "0.05",
            "exact_match_only": '["No"]',
            "exclude_incomplete_ec": '["Yes"]',
        }


class TestMergeAnalysisParams:
    """merge_analysis_params always fetches defaults, merges user params on top.

    After merge, vocab params are re-encoded as JSON arrays using the
    form metadata, ensuring user-supplied plain strings don't bypass
    the encoding required by AbstractEnumParam.convertToTerms().
    """

    def test_empty_user_params_returns_all_defaults(self) -> None:
        """When user sends no parameters, all WDK defaults are used."""
        user_params: dict[str, object] = {}
        result = merge_analysis_params(_GO_ENRICHMENT_FORM_META, user_params)
        assert result["organism"] == '["Plasmodium falciparum 3D7"]'
        assert result["pValueCutoff"] == "0.05"
        assert result["goAssociationsOntologies"] == '["Biological Process"]'
        assert result["goEvidenceCodes"] == '["all"]'
        assert result["goSubset"] == '["No"]'

    def test_user_params_override_defaults(self) -> None:
        """User-supplied parameters take precedence over WDK defaults."""
        user_params = {"pValueCutoff": "0.01"}
        result = merge_analysis_params(_GO_ENRICHMENT_FORM_META, user_params)
        assert result["organism"] == '["Plasmodium falciparum 3D7"]'
        assert result["pValueCutoff"] == "0.01"

    def test_user_plain_string_vocab_params_get_encoded(self) -> None:
        """User-supplied plain string vocab params are encoded after merge."""
        user_params = {"organism": "Plasmodium vivax P01"}
        result = merge_analysis_params(_GO_ENRICHMENT_FORM_META, user_params)
        assert result["organism"] == '["Plasmodium vivax P01"]'

    def test_nonempty_user_params_still_get_defaults(self) -> None:
        """Even when user sends some params, missing defaults are filled in."""
        user_params = {"pValueCutoff": "0.01"}
        result = merge_analysis_params(_GO_ENRICHMENT_FORM_META, user_params)
        assert result["pValueCutoff"] == "0.01"
        assert result["organism"] == '["Plasmodium falciparum 3D7"]'
        assert result["goSubset"] == '["No"]'

    def test_none_form_metadata_returns_user_params(self) -> None:
        """When form metadata is None (fetch failed), user params are used."""
        result = merge_analysis_params(None, {"pValueCutoff": "0.01"})
        assert result == {"pValueCutoff": "0.01"}

    def test_empty_search_data_returns_user_params(self) -> None:
        """When searchData has no parameters, user params are used as-is."""
        form_meta: dict[str, object] = {"searchData": {"parameters": []}}
        result = merge_analysis_params(form_meta, {"pValueCutoff": "0.01"})
        assert result == {"pValueCutoff": "0.01"}

    def test_both_empty_returns_empty(self) -> None:
        """When both defaults and user params are empty, result is empty."""
        form_meta: dict[str, object] = {"searchData": {"parameters": []}}
        result = merge_analysis_params(form_meta, {})
        assert result == {}
