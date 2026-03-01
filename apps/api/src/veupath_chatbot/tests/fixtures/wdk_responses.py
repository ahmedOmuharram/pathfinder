"""Static factory functions returning realistic WDK JSON responses.

Used by integration tests that mock HTTP responses from VEuPathDB's WDK
REST API. Each function returns a Python dict (or list) matching the
real WDK JSON structure observed in production.

Gene IDs are real *Plasmodium falciparum* 3D7 locus tags so that downstream
code that validates prefixes/formats does not trip.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Default realistic Plasmodium falciparum gene IDs
# ---------------------------------------------------------------------------
DEFAULT_GENE_IDS: list[str] = [
    "PF3D7_0100100",
    "PF3D7_0831900",
    "PF3D7_1133400",
    "PF3D7_0709000",
    "PF3D7_1343700",
]


# ---------------------------------------------------------------------------
# /users/current
# ---------------------------------------------------------------------------
def user_current_response(user_id: int = 12345) -> dict:
    """GET /users/current -- resolved guest or authenticated user."""
    return {
        "id": user_id,
        "isGuest": True,
        "email": None,
        "properties": {},
    }


# ---------------------------------------------------------------------------
# /record-types
# ---------------------------------------------------------------------------
def record_types_response() -> list:
    """GET /record-types -- list of available record types."""
    return [
        {
            "urlSegment": "gene",
            "name": "GeneRecordClasses.GeneRecordClass",
            "displayName": "Genes",
            "displayNamePlural": "Genes",
            "shortDisplayName": "Gene",
            "shortDisplayNamePlural": "Genes",
            "nativeDisplayName": "gene",
            "nativeDisplayNamePlural": "genes",
            "nativeShortDisplayName": "gene",
            "nativeShortDisplayNamePlural": "genes",
            "iconName": "gene",
            "description": "A region of the genome encoding a gene product",
            "hasAllRecordsQuery": True,
        },
        {
            "urlSegment": "transcript",
            "name": "TranscriptRecordClasses.TranscriptRecordClass",
            "displayName": "Transcripts",
            "displayNamePlural": "Transcripts",
            "shortDisplayName": "Transcript",
            "shortDisplayNamePlural": "Transcripts",
            "nativeDisplayName": "transcript",
            "nativeDisplayNamePlural": "transcripts",
            "nativeShortDisplayName": "transcript",
            "nativeShortDisplayNamePlural": "transcripts",
            "iconName": "transcript",
            "description": "An RNA product of a gene region",
            "hasAllRecordsQuery": True,
        },
    ]


# ---------------------------------------------------------------------------
# /record-types/{recordType}/searches
# ---------------------------------------------------------------------------
def searches_response() -> list:
    """GET /record-types/gene/searches -- list of search questions."""
    return [
        {
            "urlSegment": "GenesByTaxon",
            "name": "GenesByTaxon",
            "displayName": "Taxon",
            "shortDisplayName": "Taxon",
            "description": "Find genes by organism/taxon",
            "isInternal": False,
            "outputRecordClassName": "GeneRecordClasses.GeneRecordClass",
        },
        {
            "urlSegment": "GenesByTextSearch",
            "name": "GenesByTextSearch",
            "displayName": "Text search (genes)",
            "shortDisplayName": "Text",
            "description": "Find genes matching a text expression",
            "isInternal": False,
            "outputRecordClassName": "GeneRecordClasses.GeneRecordClass",
        },
        {
            "urlSegment": "boolean_question_GeneRecordClasses.GeneRecordClass",
            "name": "boolean_question_GeneRecordClasses.GeneRecordClass",
            "displayName": "Combine",
            "shortDisplayName": "Combine",
            "description": "Boolean combination of gene searches",
            "isInternal": True,
            "outputRecordClassName": "GeneRecordClasses.GeneRecordClass",
        },
        {
            "urlSegment": "GenesByOrthologs",
            "name": "GenesByOrthologs",
            "displayName": "Orthologs",
            "shortDisplayName": "Orthologs",
            "description": "Find genes by ortholog transform",
            "isInternal": False,
            "outputRecordClassName": "GeneRecordClasses.GeneRecordClass",
        },
    ]


# ---------------------------------------------------------------------------
# /record-types/{recordType}/searches/{searchName}  (with expandParams)
# ---------------------------------------------------------------------------
def search_details_response(search_name: str = "GenesByTaxon") -> dict:
    """GET /record-types/gene/searches/{searchName}?expandParams=true."""
    if search_name == "boolean_question_GeneRecordClasses.GeneRecordClass":
        return _boolean_search_details()
    if search_name == "GenesByTextSearch":
        return _text_search_details()
    if search_name == "GenesByOrthologs":
        return _orthologs_search_details()
    # Default: GenesByTaxon
    return _taxon_search_details()


def _taxon_search_details() -> dict:
    return {
        "urlSegment": "GenesByTaxon",
        "name": "GenesByTaxon",
        "displayName": "Taxon",
        "description": "Find genes by organism/taxon",
        "isInternal": False,
        "outputRecordClassName": "GeneRecordClasses.GeneRecordClass",
        "searchData": {
            "paramNames": ["organism"],
            "defaultParamValues": {
                "organism": '["Plasmodium falciparum 3D7"]',
            },
            "parameters": [
                {
                    "name": "organism",
                    "displayName": "Organism",
                    "type": "multi-pick-vocabulary",
                    "allowEmptyValue": False,
                    "minSelectedCount": 1,
                    "maxSelectedCount": None,
                    "countOnlyLeaves": True,
                    "vocabulary": {
                        "data": {
                            "display": "Plasmodium",
                            "term": "Plasmodium",
                        },
                        "children": [
                            {
                                "data": {
                                    "display": "Plasmodium falciparum 3D7",
                                    "term": "Plasmodium falciparum 3D7",
                                },
                                "children": [],
                            },
                            {
                                "data": {
                                    "display": "Plasmodium vivax P01",
                                    "term": "Plasmodium vivax P01",
                                },
                                "children": [],
                            },
                        ],
                    },
                },
            ],
        },
    }


def _text_search_details() -> dict:
    return {
        "urlSegment": "GenesByTextSearch",
        "name": "GenesByTextSearch",
        "displayName": "Text search (genes)",
        "description": "Find genes matching a text expression",
        "isInternal": False,
        "outputRecordClassName": "GeneRecordClasses.GeneRecordClass",
        "searchData": {
            "paramNames": [
                "text_expression",
                "text_fields",
                "text_search_organism",
                "document_type",
            ],
            "defaultParamValues": {
                "text_expression": "",
                "text_fields": '["primary_key","Alias"]',
                "text_search_organism": '["Plasmodium falciparum 3D7"]',
                "document_type": "gene",
            },
            "parameters": [
                {
                    "name": "text_expression",
                    "displayName": "Text expression",
                    "type": "string",
                    "allowEmptyValue": False,
                },
                {
                    "name": "text_fields",
                    "displayName": "Fields to search",
                    "type": "multi-pick-vocabulary",
                    "allowEmptyValue": False,
                    "minSelectedCount": 1,
                    "vocabulary": [
                        ["primary_key", "Gene ID"],
                        ["Alias", "Gene alias"],
                        ["product", "Product description"],
                        ["GOTerms", "GO terms"],
                        ["Notes", "Notes"],
                    ],
                },
                {
                    "name": "text_search_organism",
                    "displayName": "Organism",
                    "type": "multi-pick-vocabulary",
                    "allowEmptyValue": False,
                    "minSelectedCount": 1,
                    "vocabulary": [
                        [
                            "Plasmodium falciparum 3D7",
                            "Plasmodium falciparum 3D7",
                        ],
                    ],
                },
                {
                    "name": "document_type",
                    "displayName": "Document type",
                    "type": "single-pick-vocabulary",
                    "allowEmptyValue": False,
                    "vocabulary": [
                        ["gene", "Gene"],
                        ["est", "EST"],
                    ],
                },
            ],
        },
    }


def _boolean_search_details() -> dict:
    suffix = "GeneRecordClasses.GeneRecordClass"
    return {
        "urlSegment": f"boolean_question_{suffix}",
        "name": f"boolean_question_{suffix}",
        "displayName": "Combine",
        "description": "Boolean combination of gene searches",
        "isInternal": True,
        "outputRecordClassName": suffix,
        "searchData": {
            "paramNames": [
                f"bq_left_op__{suffix}",
                f"bq_right_op__{suffix}",
                "bq_operator",
            ],
            "defaultParamValues": {
                f"bq_left_op__{suffix}": "",
                f"bq_right_op__{suffix}": "",
                "bq_operator": "INTERSECT",
            },
            "parameters": [
                {
                    "name": f"bq_left_op__{suffix}",
                    "displayName": "Left operand",
                    "type": "input-step",
                    "allowEmptyValue": True,
                },
                {
                    "name": f"bq_right_op__{suffix}",
                    "displayName": "Right operand",
                    "type": "input-step",
                    "allowEmptyValue": True,
                },
                {
                    "name": "bq_operator",
                    "displayName": "Operator",
                    "type": "single-pick-vocabulary",
                    "allowEmptyValue": False,
                    "vocabulary": [
                        ["INTERSECT", "Intersect"],
                        ["UNION", "Union"],
                        ["MINUS", "Minus"],
                        ["RMINUS", "Right minus"],
                        ["LONLY", "Left only"],
                        ["RONLY", "Right only"],
                    ],
                },
            ],
        },
    }


def _orthologs_search_details() -> dict:
    return {
        "urlSegment": "GenesByOrthologs",
        "name": "GenesByOrthologs",
        "displayName": "Orthologs",
        "description": "Find genes by ortholog transform",
        "isInternal": False,
        "outputRecordClassName": "GeneRecordClasses.GeneRecordClass",
        "searchData": {
            "paramNames": ["inputStepId", "organism", "isSyntenic"],
            "defaultParamValues": {
                "inputStepId": "",
                "organism": '["Plasmodium falciparum 3D7"]',
                "isSyntenic": "no",
            },
            "parameters": [
                {
                    "name": "inputStepId",
                    "displayName": "Input step",
                    "type": "input-step",
                    "allowEmptyValue": True,
                },
                {
                    "name": "organism",
                    "displayName": "Organism",
                    "type": "multi-pick-vocabulary",
                    "allowEmptyValue": False,
                    "minSelectedCount": 1,
                    "vocabulary": [
                        [
                            "Plasmodium falciparum 3D7",
                            "Plasmodium falciparum 3D7",
                        ],
                        [
                            "Plasmodium vivax P01",
                            "Plasmodium vivax P01",
                        ],
                    ],
                },
                {
                    "name": "isSyntenic",
                    "displayName": "Syntenic",
                    "type": "single-pick-vocabulary",
                    "allowEmptyValue": True,
                    "vocabulary": [
                        ["yes", "yes"],
                        ["no", "no"],
                    ],
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# POST /users/{userId}/steps  -- step creation
# ---------------------------------------------------------------------------
def step_creation_response(step_id: int = 100) -> dict:
    """POST /users/{userId}/steps -- returns created step."""
    return {"id": step_id}


# ---------------------------------------------------------------------------
# POST /users/{userId}/strategies  -- strategy creation
# ---------------------------------------------------------------------------
def strategy_creation_response(strategy_id: int = 200) -> dict:
    """POST /users/{userId}/strategies -- returns created strategy."""
    return {"id": strategy_id}


# ---------------------------------------------------------------------------
# GET /users/{userId}/strategies/{strategyId}
# ---------------------------------------------------------------------------
def strategy_get_response(
    strategy_id: int = 200,
    step_ids: list[int] | None = None,
) -> dict:
    """GET /users/{userId}/strategies/{strategyId} -- full strategy.

    Builds a linear chain strategy by default: step_ids[0] is a leaf,
    each subsequent step is a combine with its predecessor.
    """
    ids = step_ids or [100, 101, 102]

    # Build stepTree: for a single step, just one node.
    # For multiple steps, rightmost is root with a chain of primaryInput.
    def _build_tree(remaining: list[int]) -> dict:
        if len(remaining) == 1:
            return {"stepId": remaining[0]}
        return {
            "stepId": remaining[-1],
            "primaryInput": _build_tree(remaining[:-1]),
        }

    step_tree = _build_tree(ids)

    # Build steps map  --  step_id -> step summary
    steps: dict[str, dict] = {}
    for i, sid in enumerate(ids):
        is_combined = i > 0
        step_entry: dict = {
            "id": sid,
            "customName": f"Step {i + 1}",
            "displayName": f"Step {i + 1}",
            "isFiltered": False,
            "estimatedSize": 150 - i * 30,
            "hasCompleteStepAnalyses": False,
            "recordClassName": "GeneRecordClasses.GeneRecordClass",
        }
        if is_combined:
            step_entry["searchName"] = (
                "boolean_question_GeneRecordClasses.GeneRecordClass"
            )
            step_entry["searchConfig"] = {
                "parameters": {
                    "bq_left_op__GeneRecordClasses.GeneRecordClass": "",
                    "bq_right_op__GeneRecordClasses.GeneRecordClass": "",
                    "bq_operator": "INTERSECT",
                },
            }
        else:
            step_entry["searchName"] = "GenesByTaxon"
            step_entry["searchConfig"] = {
                "parameters": {
                    "organism": '["Plasmodium falciparum 3D7"]',
                },
            }
        steps[str(sid)] = step_entry

    return {
        "strategyId": strategy_id,
        "name": "Test strategy",
        "description": None,
        "isSaved": False,
        "isPublic": False,
        "isDeleted": False,
        "isValid": True,
        "rootStepId": ids[-1],
        "estimatedSize": 150,
        "recordClassName": "GeneRecordClasses.GeneRecordClass",
        "stepTree": step_tree,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# Standard reporter response -- POST .../reports/standard
# ---------------------------------------------------------------------------
def standard_report_response(
    gene_ids: list[str] | None = None,
    total_count: int | None = None,
) -> dict:
    """POST .../reports/standard -- paginated records response."""
    ids = gene_ids if gene_ids is not None else DEFAULT_GENE_IDS
    count = total_count if total_count is not None else len(ids)

    records = []
    for gid in ids:
        records.append(
            {
                "id": [
                    {"name": "gene_source_id", "value": gid},
                ],
                "displayName": gid,
                "recordClassName": "GeneRecordClasses.GeneRecordClass",
                "attributes": {
                    "primary_key": gid,
                    "gene_source_id": gid,
                    "gene_name": None,
                    "gene_product": f"hypothetical protein, conserved ({gid})",
                    "gene_type": "protein_coding",
                    "organism": "Plasmodium falciparum 3D7",
                    "gene_location_text": "Pf3D7_01_v3: 29,510 - 37,126 (+)",
                    "gene_previous_ids": "",
                },
                "tables": {},
                "tableErrors": [],
            }
        )

    return {
        "records": records,
        "meta": {
            "totalCount": count,
            "displayedCount": len(ids),
            "viewTotalCount": count,
            "responseCount": len(ids),
        },
    }


# ---------------------------------------------------------------------------
# POST /users/{userId}/datasets
# ---------------------------------------------------------------------------
def dataset_creation_response(dataset_id: int = 500) -> dict:
    """POST /users/{userId}/datasets -- returns new dataset."""
    return {"id": dataset_id}


# ---------------------------------------------------------------------------
# POST /users/{userId}/steps/{stepId}/analyses  -- analysis creation
# ---------------------------------------------------------------------------
def analysis_create_response(analysis_id: int = 300) -> dict:
    """POST .../analyses -- returns new analysis instance."""
    return {
        "analysisId": analysis_id,
        "displayName": "GO enrichment",
        "isNew": True,
        "status": "CREATED",
    }


# ---------------------------------------------------------------------------
# GET .../analyses/{analysisId}/result/status
# ---------------------------------------------------------------------------
def analysis_status_response(status: str = "COMPLETE") -> dict:
    """GET .../analyses/{analysisId}/result/status."""
    return {"status": status}


# ---------------------------------------------------------------------------
# GET .../analyses/{analysisId}/result  -- enrichment-like result
# ---------------------------------------------------------------------------
def analysis_result_response() -> dict:
    """GET .../analyses/{analysisId}/result -- GO enrichment result.

    Contains realistic GO enrichment rows for *Plasmodium falciparum*.
    """
    return {
        "resultSize": 42,
        "backgroundSize": 5305,
        "rows": [
            {
                "ID": "GO:0003735",
                "Description": "structural constituent of ribosome",
                "ResultCount": 12,
                "BgdCount": 88,
                "FoldEnrich": 2.41,
                "OddsRatio": 2.95,
                "PValue": 3.2e-5,
                "BenjaminiHochberg": 1.1e-3,
                "Bonferroni": 4.8e-3,
                "ResultIDList": "PF3D7_0100100,PF3D7_0831900,PF3D7_1133400",
            },
            {
                "ID": "GO:0006412",
                "Description": "translation",
                "ResultCount": 15,
                "BgdCount": 140,
                "FoldEnrich": 1.89,
                "OddsRatio": 2.17,
                "PValue": 8.4e-4,
                "BenjaminiHochberg": 1.5e-2,
                "Bonferroni": 7.6e-2,
                "ResultIDList": "PF3D7_0709000,PF3D7_1343700,PF3D7_0100100",
            },
            {
                "ID": "GO:0005840",
                "Description": "ribosome",
                "ResultCount": 10,
                "BgdCount": 72,
                "FoldEnrich": 2.45,
                "OddsRatio": 3.01,
                "PValue": 1.7e-4,
                "BenjaminiHochberg": 3.9e-3,
                "Bonferroni": 2.1e-2,
                "ResultIDList": "PF3D7_0831900,PF3D7_1133400",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------
def error_response_422() -> dict:
    """WDK 422 Unprocessable Entity -- validation error."""
    return {
        "status": "unprocessable_entity",
        "message": "Validation failed",
        "errors": {
            "general": [],
            "byKey": {
                "organism": [
                    "Required parameter 'organism' is missing or empty.",
                ],
            },
        },
    }


def error_response_404() -> dict:
    """WDK 404 Not Found -- resource does not exist."""
    return {
        "status": "not_found",
        "message": "Step 99999 not found for user 12345",
    }
