"""Static factory functions returning realistic WDK JSON responses.

Used by integration tests that mock HTTP responses from VEuPathDB's WDK
REST API. Each function returns a Python dict (or list) matching the
real WDK JSON structure observed in production.

Gene IDs are real *Plasmodium falciparum* 3D7 locus tags so that downstream
code that validates prefixes/formats does not trip.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StrategyItemDetails:
    """Optional details for :func:`strategy_list_item`.

    Groups classification and metadata fields that are rarely overridden
    so the builder stays within the six-argument limit.
    """

    record_class_name: str = "TranscriptRecordClasses.TranscriptRecordClass"
    estimated_size: int = 150
    is_saved: bool = False
    signature: str = "abc123def456"
    leaf_and_transform_step_count: int = field(default=1)


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
# /record-types  (non-expanded: plain strings; expanded: objects with urlSegment)
# ---------------------------------------------------------------------------
def record_types_response() -> list:
    """GET /record-types -- plain string list of available record types.

    The real WDK endpoint returns a flat list of strings when called
    without ``?format=expanded``.  With ``?format=expanded`` it returns
    objects with ``urlSegment``, ``fullName``, ``displayName``, etc.
    """
    return [
        "transcript",
        "gene",
        "organism",
        "popsetSequence",
        "sample",
        "genomic-sequence",
    ]


def record_types_expanded_response() -> list:
    """GET /record-types?format=expanded -- objects with full metadata."""
    return [
        {
            "urlSegment": "transcript",
            "fullName": "TranscriptRecordClasses.TranscriptRecordClass",
            "displayName": "Gene",
            "displayNamePlural": "Genes",
            "shortDisplayName": "Gene",
            "shortDisplayNamePlural": "Genes",
            "nativeDisplayName": "Transcript",
            "nativeDisplayNamePlural": "Transcripts",
            "nativeShortDisplayName": "Transcript",
            "nativeShortDisplayNamePlural": "Transcripts",
            "description": "",
            "hasAllRecordsQuery": True,
            "recordIdAttributeName": "primary_key",
            "primaryKeyColumnRefs": ["gene_source_id", "source_id", "project_id"],
            "useBasket": True,
        },
        {
            "urlSegment": "gene",
            "fullName": "GeneRecordClasses.GeneRecordClass",
            "displayName": "Gene",
            "displayNamePlural": "Genes",
            "shortDisplayName": "Gene",
            "shortDisplayNamePlural": "Genes",
            "nativeDisplayName": "Gene",
            "nativeDisplayNamePlural": "Genes",
            "nativeShortDisplayName": "Gene",
            "nativeShortDisplayNamePlural": "Genes",
            "description": "",
            "hasAllRecordsQuery": True,
            "recordIdAttributeName": "source_id",
            "primaryKeyColumnRefs": ["source_id", "project_id"],
            "useBasket": True,
        },
    ]


# ---------------------------------------------------------------------------
# /record-types/{recordType}/searches
# ---------------------------------------------------------------------------
def searches_response() -> list:
    """GET /record-types/transcript/searches -- list of search questions.

    Real WDK search list items have these keys (confirmed via live CURL):
      urlSegment, fullName, queryName, displayName, shortDisplayName,
      outputRecordClassName, paramNames, isAnalyzable, isCacheable,
      defaultAttributes, defaultSorting, defaultSummaryView,
      dynamicAttributes, filters, groups, properties, summaryViewPlugins,
      noSummaryOnSingleRecord

    Notably ABSENT from the list endpoint: ``name``, ``isInternal``, ``description``.
    The ``description`` field appears on *some* searches (transforms) but not others.
    The ``isInternal`` field is NEVER present in the list -- use ``fullName``
    starting with ``"InternalQuestions."`` as the indicator.
    Boolean search ``urlSegment`` uses underscores, not dots.
    """
    return [
        {
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
            "defaultAttributes": ["primary_key", "organism", "gene_product"],
            "defaultSorting": [
                {"attributeName": "organism", "direction": "ASC"},
            ],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        {
            "urlSegment": "GenesByTextSearch",
            "fullName": "GeneQuestions.GenesByTextSearch",
            "queryName": "GenesByTextSearch",
            "displayName": "Text search (genes)",
            "shortDisplayName": "Text",
            "outputRecordClassName": "transcript",
            "paramNames": [
                "text_expression",
                "text_fields",
                "text_search_organism",
                "document_type",
            ],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "gene_product"],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        {
            # Boolean search: urlSegment uses underscores (not dots).
            # fullName starts with "InternalQuestions." indicating internal.
            "urlSegment": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
            "fullName": "InternalQuestions.boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
            "queryName": "bq_TranscriptRecordClasses_TranscriptRecordClass",
            "displayName": "Combine Gene results",
            "shortDisplayName": "Combine Gene results",
            "outputRecordClassName": "transcript",
            "paramNames": [
                "bq_left_op_TranscriptRecordClasses_TranscriptRecordClass",
                "bq_right_op_TranscriptRecordClasses_TranscriptRecordClass",
                "bq_operator",
            ],
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
            # Boolean searches have these extra fields:
            "allowedPrimaryInputRecordClassNames": ["transcript"],
            "allowedSecondaryInputRecordClassNames": ["transcript"],
        },
        {
            "urlSegment": "GenesByOrthologs",
            "fullName": "GeneQuestions.GenesByOrthologs",
            "queryName": "GenesByOrthologs",
            "displayName": "Orthologs",
            "shortDisplayName": "Orthologs",
            "description": "Find genes by ortholog transform",
            "outputRecordClassName": "transcript",
            "paramNames": ["inputStepId", "organism", "isSyntenic"],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "gene_product"],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
    ]


# ---------------------------------------------------------------------------
# /record-types/{recordType}/searches/{searchName}  (with expandParams)
# ---------------------------------------------------------------------------
def search_details_response(search_name: str = "GenesByTaxon") -> dict:
    """GET /record-types/transcript/searches/{searchName}?expandParams=true.

    Real WDK response has TWO top-level keys:
      ``searchData`` -- the full search metadata including expanded parameters
      ``validation``  -- ``{level, isValid}``

    There is NO top-level ``name``, ``isInternal``, or ``outputRecordClassName``.
    Those fields live inside ``searchData``.

    Inside each parameter, default values come from ``initialDisplayValue``
    (not a ``defaultParamValues`` dict on searchData).

    Vocabulary entries are always 3-element arrays ``[term, display, parent]``
    (parent is usually ``null``).
    """
    boolean_name = "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"
    if search_name == boolean_name:
        return _boolean_search_details()
    if search_name == "GenesByTextSearch":
        return _text_search_details()
    if search_name == "GenesByOrthologs":
        return _orthologs_search_details()
    # Default fallback is GenesByTaxon
    return _taxon_search_details()


def _taxon_search_details() -> dict:
    return {
        "searchData": {
            "urlSegment": "GenesByTaxon",
            "fullName": "GeneQuestions.GenesByTaxon",
            "queryName": "GenesByTaxon",
            "displayName": "Organism",
            "shortDisplayName": "Organism",
            "summary": "Find all genes from one or more species/organism.",
            "description": "Find all genes from one or more species/organism.",
            "outputRecordClassName": "transcript",
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "organism", "gene_product"],
            "defaultSorting": [
                {"attributeName": "organism", "direction": "ASC"},
            ],
            "paramNames": ["organism"],
            "parameters": [
                {
                    "name": "organism",
                    "displayName": "Organism",
                    "type": "multi-pick-vocabulary",
                    "displayType": "treeBox",
                    "allowEmptyValue": False,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": '["Plasmodium falciparum 3D7"]',
                    "minSelectedCount": 1,
                    "maxSelectedCount": -1,
                    "countOnlyLeaves": True,
                    "depthExpanded": 0,
                    "dependentParams": [],
                    "group": "empty",
                    "properties": {},
                    # Tree-shaped vocabulary for treeBox display
                    "vocabulary": {
                        "data": {
                            "display": "@@fake@@",
                            "term": "@@fake@@",
                        },
                        "children": [
                            {
                                "data": {
                                    "display": "Plasmodiidae",
                                    "term": "Plasmodiidae",
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
                        ],
                    },
                },
            ],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        "validation": {
            "level": "DISPLAYABLE",
            "isValid": True,
        },
    }


def _text_search_details() -> dict:
    return {
        "searchData": {
            "urlSegment": "GenesByTextSearch",
            "fullName": "GeneQuestions.GenesByTextSearch",
            "queryName": "GenesByTextSearch",
            "displayName": "Text search (genes)",
            "shortDisplayName": "Text",
            "summary": "Find genes matching a text expression",
            "description": "Find genes matching a text expression",
            "outputRecordClassName": "transcript",
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "gene_product"],
            "defaultSorting": [],
            "paramNames": [
                "text_expression",
                "text_fields",
                "text_search_organism",
                "document_type",
            ],
            "parameters": [
                {
                    "name": "text_expression",
                    "displayName": "Text expression",
                    "type": "string",
                    "allowEmptyValue": False,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": "",
                    "dependentParams": [],
                    "properties": {},
                },
                {
                    "name": "text_fields",
                    "displayName": "Fields to search",
                    "type": "multi-pick-vocabulary",
                    "allowEmptyValue": False,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": '["primary_key","Alias"]',
                    "minSelectedCount": 1,
                    "maxSelectedCount": -1,
                    "dependentParams": [],
                    "properties": {},
                    # Flat list vocabulary: [term, display, parent]
                    "vocabulary": [
                        ["primary_key", "Gene ID", None],
                        ["Alias", "Gene alias", None],
                        ["product", "Product description", None],
                        ["GOTerms", "GO terms", None],
                        ["Notes", "Notes", None],
                    ],
                },
                {
                    "name": "text_search_organism",
                    "displayName": "Organism",
                    "type": "multi-pick-vocabulary",
                    "allowEmptyValue": False,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": '["Plasmodium falciparum 3D7"]',
                    "minSelectedCount": 1,
                    "maxSelectedCount": -1,
                    "dependentParams": [],
                    "properties": {},
                    "vocabulary": [
                        [
                            "Plasmodium falciparum 3D7",
                            "Plasmodium falciparum 3D7",
                            None,
                        ],
                    ],
                },
                {
                    "name": "document_type",
                    "displayName": "Document type",
                    "type": "single-pick-vocabulary",
                    "allowEmptyValue": False,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": "gene",
                    "minSelectedCount": 1,
                    "maxSelectedCount": 1,
                    "dependentParams": [],
                    "properties": {},
                    "vocabulary": [
                        ["gene", "Gene", None],
                        ["est", "EST", None],
                    ],
                },
            ],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        "validation": {
            "level": "DISPLAYABLE",
            "isValid": True,
        },
    }


def _boolean_search_details() -> dict:
    # Real PlasmoDB uses underscores in urlSegment and param names (not dots).
    suffix = "TranscriptRecordClasses_TranscriptRecordClass"
    return {
        "searchData": {
            "urlSegment": f"boolean_question_{suffix}",
            "fullName": f"InternalQuestions.boolean_question_{suffix}",
            "queryName": f"bq_{suffix}",
            "displayName": "Combine Gene results",
            "shortDisplayName": "Combine Gene results",
            "outputRecordClassName": "transcript",
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": [],
            "defaultSorting": [],
            "paramNames": [
                f"bq_left_op_{suffix}",
                f"bq_right_op_{suffix}",
                "bq_operator",
            ],
            "parameters": [
                {
                    "name": f"bq_left_op_{suffix}",
                    "displayName": "Left operand",
                    "type": "input-step",
                    "allowEmptyValue": True,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": "",
                    "dependentParams": [],
                    "properties": {},
                },
                {
                    "name": f"bq_right_op_{suffix}",
                    "displayName": "Right operand",
                    "type": "input-step",
                    "allowEmptyValue": True,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": "",
                    "dependentParams": [],
                    "properties": {},
                },
                {
                    "name": "bq_operator",
                    "displayName": "Operator",
                    "type": "single-pick-vocabulary",
                    "allowEmptyValue": False,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": "INTERSECT",
                    "minSelectedCount": 1,
                    "maxSelectedCount": 1,
                    "dependentParams": [],
                    "properties": {},
                    # Real WDK vocab: [term, display, parent]
                    "vocabulary": [
                        ["UNION", "UNION", None],
                        ["INTERSECT", "INTERSECT", None],
                        ["MINUS", "LEFT_MINUS", None],
                        ["RMINUS", "RIGHT_MINUS", None],
                        ["LONLY", "LEFT_ONLY", None],
                        ["RONLY", "RIGHT_ONLY", None],
                    ],
                },
            ],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        "validation": {
            "level": "DISPLAYABLE",
            "isValid": True,
        },
    }


def _orthologs_search_details() -> dict:
    return {
        "searchData": {
            "urlSegment": "GenesByOrthologs",
            "fullName": "GeneQuestions.GenesByOrthologs",
            "queryName": "GenesByOrthologs",
            "displayName": "Orthologs",
            "shortDisplayName": "Orthologs",
            "summary": "Find genes by ortholog transform",
            "description": "Find genes by ortholog transform",
            "outputRecordClassName": "transcript",
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "gene_product"],
            "defaultSorting": [],
            "paramNames": ["inputStepId", "organism", "isSyntenic"],
            "parameters": [
                {
                    "name": "inputStepId",
                    "displayName": "Input step",
                    "type": "input-step",
                    "allowEmptyValue": True,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": "",
                    "dependentParams": [],
                    "properties": {},
                },
                {
                    "name": "organism",
                    "displayName": "Organism",
                    "type": "multi-pick-vocabulary",
                    "allowEmptyValue": False,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": '["Plasmodium falciparum 3D7"]',
                    "minSelectedCount": 1,
                    "maxSelectedCount": -1,
                    "dependentParams": [],
                    "properties": {},
                    "vocabulary": [
                        [
                            "Plasmodium falciparum 3D7",
                            "Plasmodium falciparum 3D7",
                            None,
                        ],
                        [
                            "Plasmodium vivax P01",
                            "Plasmodium vivax P01",
                            None,
                        ],
                    ],
                },
                {
                    "name": "isSyntenic",
                    "displayName": "Syntenic",
                    "type": "single-pick-vocabulary",
                    "allowEmptyValue": True,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": "no",
                    "minSelectedCount": 1,
                    "maxSelectedCount": 1,
                    "dependentParams": [],
                    "properties": {},
                    "vocabulary": [
                        ["yes", "yes", None],
                        ["no", "no", None],
                    ],
                },
            ],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        "validation": {
            "level": "DISPLAYABLE",
            "isValid": True,
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
# Strategy detail endpoint (GET strategy by ID)
# ---------------------------------------------------------------------------
def strategy_get_response(
    strategy_id: int = 200,
    step_ids: list[int] | None = None,
) -> dict:
    """GET /users/{userId}/strategies/{strategyId} -- detailed strategy.

    Real WDK strategy GET response includes a ``steps`` dict keyed by
    step ID strings, each containing full step detail objects. Also
    includes ``stepTree``, ``author``, ``organization``, ``releaseVersion``,
    ``lastModified``, ``lastViewed``, ``leafAndTransformStepCount``,
    ``nameOfFirstStep``, etc.

    The ``stepTree`` is a recursive structure with ``stepId``,
    ``primaryInput``, and optionally ``secondaryInput``.
    """
    ids = step_ids or [100, 101, 102]

    search_names = {
        0: "GenesByTaxon",
        1: "GenesByTextSearch",
        2: "GenesByOrthologs",
    }

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

    # Build steps dict keyed by step ID strings
    steps: dict[str, dict] = {}
    for idx, sid in enumerate(ids):
        sname = search_names.get(idx, "GenesByTaxon")
        steps[str(sid)] = {
            "id": sid,
            "searchName": sname,
            "searchConfig": {
                "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                "wdkWeight": 0,
            },
            "displayName": "Organism" if sname == "GenesByTaxon" else sname,
            "customName": None,
            "estimatedSize": 150,
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "isFiltered": False,
            "hasCompleteStepAnalyses": False,
        }

    return {
        "strategyId": strategy_id,
        "name": "Test strategy",
        "description": "",
        "author": "Guest User",
        "organization": "",
        "releaseVersion": "68",
        "isSaved": False,
        "isPublic": False,
        "isDeleted": False,
        "isValid": True,
        "isExample": False,
        "rootStepId": ids[-1],
        "estimatedSize": 150,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "stepTree": step_tree,
        "steps": steps,
        "signature": "abc123def456",
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
        "lastViewed": "2026-03-06T00:00:00Z",
        "leafAndTransformStepCount": len(ids),
        "nameOfFirstStep": "Organism",
    }


def strategy_list_item(
    strategy_id: int = 200,
    name: str = "Test strategy",
    details: StrategyItemDetails | None = None,
) -> dict:
    """GET /users/{id}/strategies list item -- summary only, no stepTree/steps."""
    d = details or StrategyItemDetails()
    return {
        "strategyId": strategy_id,
        "name": name,
        "description": "",
        "author": "Guest User",
        "rootStepId": 100,
        "recordClassName": d.record_class_name,
        "signature": d.signature,
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
        "lastViewed": "2026-03-06T00:00:00Z",
        "releaseVersion": "68",
        "isPublic": False,
        "isSaved": d.is_saved,
        "isValid": True,
        "isDeleted": False,
        "isExample": False,
        "organization": "",
        "estimatedSize": d.estimated_size,
        "nameOfFirstStep": "Organism",
        "leafAndTransformStepCount": d.leaf_and_transform_step_count,
    }


def strategy_list_response(count: int = 3) -> list[dict]:
    """GET /users/{id}/strategies -- list of strategy summaries."""
    return [
        strategy_list_item(
            strategy_id=200 + i,
            name=f"Strategy {i + 1}",
            details=StrategyItemDetails(
                signature=f"sig{i:04d}",
                leaf_and_transform_step_count=i + 1,
            ),
        )
        for i in range(count)
    ]


def step_get_response(
    step_id: int = 100,
    search_name: str = "GenesByTaxon",
    estimated_size: int = 150,
    is_boolean: bool = False,
) -> dict:
    """GET /users/{userId}/steps/{stepId} -- individual step details.

    Step details are fetched separately from the strategy.
    """
    suffix = "TranscriptRecordClasses_TranscriptRecordClass"
    step: dict[str, Any] = {
        "id": step_id,
        "customName": f"Step for {search_name}",
        "displayName": f"Step for {search_name}",
        "isFiltered": False,
        "estimatedSize": estimated_size,
        "hasCompleteStepAnalyses": False,
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "searchName": search_name,
        "searchConfig": {
            "parameters": (
                {
                    f"bq_left_op_{suffix}": "",
                    f"bq_right_op_{suffix}": "",
                    "bq_operator": "INTERSECT",
                }
                if is_boolean
                else {"organism": '["Plasmodium falciparum 3D7"]'}
            ),
        },
    }
    return step


# ---------------------------------------------------------------------------
# Individual typed response factories
# ---------------------------------------------------------------------------


def wdk_step_json(
    *,
    step_id: int = 12345,
    search_name: str = "GenesByTaxon",
    record_class_name: str | None = "transcript",
    estimated_size: int | None = 42,
    strategy_id: int | None = 99999,
    parameters: dict[str, str] | None = None,
) -> dict[str, Any]:
    """GET /users/{id}/steps/{id} -- complete step detail.

    All field names match the real WDK REST API response confirmed via
    ``curl -s https://plasmodb.org/plasmo/service/users/current/steps/{id}``.
    """
    params = parameters or {"organism": '["Plasmodium falciparum 3D7"]'}
    return {
        "id": step_id,
        "searchName": search_name,
        "searchConfig": {
            "parameters": params,
            "wdkWeight": 0,
        },
        "recordClassName": record_class_name,
        "validation": {
            "level": "RUNNABLE",
            "isValid": True,
        },
        "estimatedSize": estimated_size,
        "strategyId": strategy_id,
        "displayName": "Organism",
        "shortDisplayName": "Organism",
        "customName": None,
        "baseCustomName": None,
        "expanded": False,
        "expandedName": None,
        "isFiltered": False,
        "description": "",
        "ownerId": 67890,
        "hasCompleteStepAnalyses": False,
        "displayPreferences": {},
        "createdTime": "2026-03-01T00:00:00Z",
        "lastRunTime": "2026-03-01T00:00:00Z",
    }


def wdk_strategy_summary_json(
    *,
    strategy_id: int = 99999,
    name: str = "Test Strategy",
    root_step_id: int = 12345,
    record_class_name: str | None = ("TranscriptRecordClasses.TranscriptRecordClass"),
    estimated_size: int | None = 150,
    is_saved: bool = False,
) -> dict[str, Any]:
    """GET /users/{id}/strategies -- single strategy summary list item.

    All field names match the real WDK REST API response confirmed via
    ``curl -s https://plasmodb.org/plasmo/service/users/current/strategies``.
    """
    return {
        "strategyId": strategy_id,
        "name": name,
        "rootStepId": root_step_id,
        "recordClassName": record_class_name,
        "signature": "abc123",
        "isSaved": is_saved,
        "isValid": True,
        "isPublic": False,
        "isDeleted": False,
        "isExample": False,
        "estimatedSize": estimated_size,
        "description": "",
        "author": "guest",
        "organization": "",
        "createdTime": "2026-03-01T00:00:00Z",
        "lastModified": "2026-03-06T00:00:00Z",
        "lastViewed": "2026-03-06T00:00:00Z",
        "releaseVersion": "68",
        "nameOfFirstStep": "Organism",
        "leafAndTransformStepCount": 1,
        "validation": {
            "level": "RUNNABLE",
            "isValid": True,
        },
    }


def wdk_strategy_details_json(
    *,
    strategy_id: int = 99999,
    name: str = "Test Strategy",
    root_step_id: int = 12345,
) -> dict[str, Any]:
    """GET /users/{id}/strategies/{id} -- full strategy with steps.

    Extends the summary shape with ``stepTree`` and ``steps`` dict (keys
    are stringified step IDs, matching real WDK behaviour).
    """
    summary = wdk_strategy_summary_json(
        strategy_id=strategy_id,
        name=name,
        root_step_id=root_step_id,
    )
    summary["stepTree"] = {
        "stepId": root_step_id,
        "primaryInput": None,
        "secondaryInput": None,
    }
    summary["steps"] = {
        str(root_step_id): wdk_step_json(step_id=root_step_id),
    }
    return summary


def wdk_answer_json(
    *,
    total_count: int = 5432,
    response_count: int = 20,
    gene_ids: list[str] | None = None,
    record_class_name: str = "transcript",
) -> dict[str, Any]:
    """POST /users/{id}/steps/{id}/reports/standard -- answer/report.

    Gene IDs default to ``DEFAULT_GENE_IDS`` (sliced to *response_count*).
    Each record contains ``gene_id``, ``organism``, and ``product`` attributes
    matching the real WDK standard reporter output.
    """
    ids = gene_ids or DEFAULT_GENE_IDS[:response_count]
    records: list[dict[str, Any]] = [
        {
            "displayName": gid,
            "id": [
                {"name": "gene_source_id", "value": gid},
                {"name": "project_id", "value": "PlasmoDB"},
            ],
            "recordClassName": record_class_name,
            "attributes": {
                "gene_id": gid,
                "organism": "Plasmodium falciparum 3D7",
                "product": "hypothetical protein",
            },
            "tables": {},
            "tableErrors": [],
        }
        for gid in ids
    ]
    return {
        "meta": {
            "totalCount": total_count,
            "responseCount": len(records),
            "displayTotalCount": total_count,
            "viewTotalCount": total_count,
            "displayViewTotalCount": total_count,
            "recordClassName": record_class_name,
            "attributes": ["gene_id", "organism"],
            "tables": [],
        },
        "records": records,
    }


def wdk_validation_json(
    *,
    level: str = "RUNNABLE",
    is_valid: bool = True,
    errors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validation sub-object used in steps, strategies, and search details."""
    result: dict[str, Any] = {
        "level": level,
        "isValid": is_valid,
    }
    if not is_valid:
        result["errors"] = errors or {
            "general": ["Validation failed"],
            "byKey": {},
        }
    return result


def wdk_search_config_json(
    *,
    parameters: dict[str, str] | None = None,
    wdk_weight: int = 0,
) -> dict[str, Any]:
    """SearchConfig sub-object used inside step payloads."""
    return {
        "parameters": parameters or {},
        "wdkWeight": wdk_weight,
    }


def wdk_enum_param_json(
    *,
    name: str = "organism",
    param_type: str = "multi-pick-vocabulary",
    display_type: str = "treeBox",
    vocabulary: Any = None,
) -> dict[str, Any]:
    """Full enum parameter matching WDK ``/searches/{name}?expandParams=true``.

    When *vocabulary* is ``None`` the default depends on *display_type*:
    - ``"treeBox"`` -- a small tree structure with ``data``/``children`` nodes.
    - anything else -- a flat 3-element list ``[term, display, parent]``.
    """
    if vocabulary is not None:
        vocab = vocabulary
    elif display_type == "treeBox":
        vocab = {
            "data": {"display": "@@fake@@", "term": "@@fake@@"},
            "children": [
                {
                    "data": {
                        "display": "Plasmodium falciparum 3D7",
                        "term": "Plasmodium falciparum 3D7",
                    },
                    "children": [],
                },
            ],
        }
    else:
        vocab = [
            ["Plasmodium falciparum 3D7", "Plasmodium falciparum 3D7", None],
        ]
    return {
        "name": name,
        "displayName": name.replace("_", " ").title(),
        "help": None,
        "type": param_type,
        "isVisible": True,
        "group": "empty",
        "isReadOnly": False,
        "allowEmptyValue": False,
        "visibleHelp": None,
        "visibleHelpPosition": None,
        "dependentParams": [],
        "initialDisplayValue": '["Plasmodium falciparum 3D7"]',
        "properties": {},
        "displayType": display_type,
        "maxSelectedCount": -1,
        "minSelectedCount": 1,
        "vocabulary": vocab,
        "countOnlyLeaves": True,
        "depthExpanded": 0,
    }


def wdk_string_param_json(
    *,
    name: str = "text_expression",
    is_number: bool = False,
    length: int = 0,
) -> dict[str, Any]:
    """Full string parameter matching WDK expandParams output."""
    return {
        "name": name,
        "displayName": name.replace("_", " ").title(),
        "help": None,
        "type": "string",
        "isVisible": True,
        "group": "empty",
        "isReadOnly": False,
        "allowEmptyValue": False,
        "visibleHelp": None,
        "visibleHelpPosition": None,
        "dependentParams": [],
        "initialDisplayValue": "",
        "properties": {},
        "length": length,
        "isMultiLine": False,
        "isNumber": is_number,
    }


def wdk_filter_param_json(
    *,
    name: str = "gene_boolean_filter_array",
) -> dict[str, Any]:
    """Full filter parameter matching WDK expandParams output."""
    return {
        "name": name,
        "displayName": name.replace("_", " ").title(),
        "help": None,
        "type": "filter",
        "isVisible": True,
        "group": "empty",
        "isReadOnly": False,
        "allowEmptyValue": True,
        "visibleHelp": None,
        "visibleHelpPosition": None,
        "dependentParams": [],
        "initialDisplayValue": None,
        "properties": {},
        "minSelectedCount": 0,
        "ontology": [
            {
                "term": "is_boolean",
                "parent": None,
                "display": "Boolean",
                "description": None,
                "type": "string",
                "units": None,
                "precision": None,
                "isRange": False,
            },
        ],
        "values": None,
        "filterDataTypeDisplayName": None,
        "hideEmptyOntologyNodes": False,
        "sortLeavesBeforeBranches": False,
        "countPredictsAnswerCount": False,
    }


def wdk_dataset_param_json(
    *,
    name: str = "ds_gene_ids",
    record_class_name: str = "transcript",
) -> dict[str, Any]:
    """Full dataset parameter matching WDK expandParams output."""
    return {
        "name": name,
        "displayName": name.replace("_", " ").title(),
        "help": None,
        "type": "input-dataset",
        "isVisible": True,
        "group": "empty",
        "isReadOnly": False,
        "allowEmptyValue": False,
        "visibleHelp": None,
        "visibleHelpPosition": None,
        "dependentParams": [],
        "initialDisplayValue": "",
        "properties": {},
        "defaultIdList": None,
        "recordClassName": record_class_name,
        "parsers": [
            {
                "name": "list",
                "displayName": "List",
                "description": "Parse a list of delimited gene IDs",
            },
        ],
    }


def wdk_record_type_json(
    *,
    url_segment: str = "transcript",
    display_name: str = "Gene",
    searches: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Record type object matching GET /record-types?format=expanded.

    The ``searches`` field is only included when explicitly provided; the
    real WDK endpoint does not return it unless requested via expansion.
    """
    result: dict[str, Any] = {
        "urlSegment": url_segment,
        "fullName": f"TranscriptRecordClasses.{url_segment.title()}RecordClass",
        "displayName": display_name,
        "displayNamePlural": f"{display_name}s",
        "shortDisplayName": display_name,
        "description": "",
        "recordIdAttributeName": "primary_key",
        "primaryKeyColumnRefs": [
            "gene_source_id",
            "source_id",
            "project_id",
        ],
        "useBasket": True,
        "hasAllRecordsQuery": True,
        "properties": {},
    }
    if searches is not None:
        result["searches"] = searches
    return result


# ---------------------------------------------------------------------------
# Standard reporter response -- POST .../reports/standard
# ---------------------------------------------------------------------------
def standard_report_response(
    gene_ids: list[str] | None = None,
    total_count: int | None = None,
) -> dict:
    """POST .../reports/standard -- paginated records response.

    Real WDK record ``id`` field contains all primary key parts.
    For the transcript record type this is a 3-element list:
    ``[gene_source_id, source_id, project_id]``.
    """
    ids = gene_ids if gene_ids is not None else DEFAULT_GENE_IDS
    count = total_count if total_count is not None else len(ids)

    records = [
        {
            "id": [
                {"name": "gene_source_id", "value": gid},
                {"name": "source_id", "value": f"{gid}.1"},
                {"name": "project_id", "value": "PlasmoDB"},
            ],
            "displayName": gid,
            "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
            "attributes": {
                "primary_key": gid,
                "gene_source_id": gid,
                "gene_name": None,
                "gene_product": f"hypothetical protein, conserved ({gid})",
                "gene_type": "protein_coding",
                "organism": "<i>Plasmodium falciparum 3D7</i>",
                "gene_location_text": "Pf3D7_01_v3: 29,510 - 37,126 (+)",
                "gene_previous_ids": "",
            },
            "tables": {},
            "tableErrors": [],
        }
        for gid in ids
    ]

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
# Dataset creation endpoint (POST datasets)
# ---------------------------------------------------------------------------
def dataset_creation_response(dataset_id: int = 500) -> dict:
    """POST /users/{userId}/datasets -- returns new dataset."""
    return {"id": dataset_id}


# ---------------------------------------------------------------------------
# POST /users/{userId}/steps/{stepId}/analyses  -- analysis creation
# ---------------------------------------------------------------------------
def analysis_create_response(
    analysis_id: int = 300,
    step_id: int = 100,
    analysis_name: str = "go-enrichment",
) -> dict:
    """POST .../analyses -- returns new analysis instance."""
    return {
        "analysisId": analysis_id,
        "stepId": step_id,
        "analysisName": analysis_name,
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

    Uses real WDK field names verified from GoEnrichmentPlugin.java
    and live PlasmoDB response (2026-03-22). All values are strings.
    """
    return {
        "resultData": [
            {
                "goId": "GO:0003735",
                "goTerm": "structural constituent of ribosome",
                "bgdGenes": "88",
                "resultGenes": "<a href='?idList=PF3D7_0100100,PF3D7_0831900,PF3D7_1133400&autoRun=1'>12</a>",
                "percentInResult": "28.6",
                "foldEnrich": "2.41",
                "oddsRatio": "2.95",
                "pValue": "3.2e-5",
                "benjamini": "1.1e-3",
                "bonferroni": "4.8e-3",
            },
            {
                "goId": "GO:0005840",
                "goTerm": "ribosome",
                "bgdGenes": "140",
                "resultGenes": "<a href='?idList=PF3D7_0709000,PF3D7_1343700,PF3D7_0100100&autoRun=1'>15</a>",
                "percentInResult": "35.7",
                "foldEnrich": "1.89",
                "oddsRatio": "2.03",
                "pValue": "8.7e-4",
                "benjamini": "1.5e-2",
                "bonferroni": "7.6e-2",
            },
            {
                "goId": "GO:0006412",
                "goTerm": "translation",
                "bgdGenes": "72",
                "resultGenes": "<a href='?idList=PF3D7_0831900,PF3D7_1133400&autoRun=1'>10</a>",
                "percentInResult": "23.8",
                "foldEnrich": "2.45",
                "oddsRatio": "2.92",
                "pValue": "9.5e-4",
                "benjamini": "3.9e-3",
                "bonferroni": "2.1e-2",
            },
        ],
        "downloadPath": "goEnrichmentResult.tsv",
        "pvalueCutoff": "0.05",
        "goTermBaseUrl": "http://amigo.geneontology.org/amigo/term/",
    }


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# POST .../columns/{col}/reports/byValue  -- column distribution
# ---------------------------------------------------------------------------
def column_distribution_response_string() -> dict:
    """POST .../columns/{col}/reports/byValue -- string column distribution.

    Returns discrete histogram bins with one entry per distinct value.
    """
    return {
        "histogram": [
            {
                "value": 2890,
                "binStart": "Plasmodium falciparum 3D7",
                "binEnd": "Plasmodium falciparum 3D7",
                "binLabel": "Plasmodium falciparum 3D7",
            },
            {
                "value": 1452,
                "binStart": "Plasmodium vivax P01",
                "binEnd": "Plasmodium vivax P01",
                "binLabel": "Plasmodium vivax P01",
            },
            {
                "value": 87,
                "binStart": "Plasmodium knowlesi H",
                "binEnd": "Plasmodium knowlesi H",
                "binLabel": "Plasmodium knowlesi H",
            },
        ],
        "statistics": {
            "subsetSize": 4429,
            "numVarValues": 4429,
            "numDistinctValues": 3,
            "numDistinctEntityRecords": 4429,
            "numMissingCases": 0,
        },
    }


def column_distribution_response_number() -> dict:
    """POST .../columns/{col}/reports/byValue -- number column distribution.

    Returns binned histogram with ranges.
    """
    return {
        "histogram": [
            {
                "value": 350,
                "binStart": "0.0",
                "binEnd": "5.0",
                "binLabel": "[0.0, 5.0)",
            },
            {
                "value": 1200,
                "binStart": "5.0",
                "binEnd": "10.0",
                "binLabel": "[5.0, 10.0)",
            },
            {
                "value": 800,
                "binStart": "10.0",
                "binEnd": "15.0",
                "binLabel": "[10.0, 15.0)",
            },
            {
                "value": 120,
                "binStart": "15.0",
                "binEnd": "20.0",
                "binLabel": "[15.0, 20.0)",
            },
        ],
        "statistics": {
            "subsetSize": 2470,
            "subsetMin": 0.5,
            "subsetMax": 18.7,
            "subsetMean": 7.3,
            "numVarValues": 2470,
            "numDistinctValues": 185,
            "numDistinctEntityRecords": 2470,
            "numMissingCases": 15,
        },
    }


# ---------------------------------------------------------------------------
# GET /users/{userId}/steps/{stepId}/analysis-types/{name}  -- form metadata
# ---------------------------------------------------------------------------
def pathway_enrichment_form_response() -> dict:
    """GET .../analysis-types/pathway-enrichment -- form metadata.

    Matches the real WDK response from PlasmoDB (curled 2026-03-04).
    WDK ``EnumParamFormatter.getParamType()`` emits JSON type strings:
    - ``"single-pick-vocabulary"`` for single-pick enum/vocab params
    - ``"multi-pick-vocabulary"`` for multi-pick enum/vocab params
    - ``"number"`` for NumberParam
    These are the only types that need JSON array encoding (they extend
    ``AbstractEnumParam`` and use ``convertToTerms()``).
    """
    return {
        "searchData": {
            "name": "pathway-enrichment",
            "displayName": "Metabolic Pathway Enrichment",
            "parameters": [
                {
                    "name": "organism",
                    "displayName": "Organism",
                    "type": "single-pick-vocabulary",
                    "initialDisplayValue": "Plasmodium falciparum 3D7",
                    "isVisible": True,
                    "minSelectedCount": 1,
                    "maxSelectedCount": 1,
                },
                {
                    "name": "pathwaysSources",
                    "displayName": "Pathway Sources",
                    "type": "multi-pick-vocabulary",
                    "initialDisplayValue": '["KEGG","MetaCyc"]',
                    "isVisible": True,
                    "minSelectedCount": 1,
                    "maxSelectedCount": -1,
                },
                {
                    "name": "pValueCutoff",
                    "displayName": "P-Value cutoff",
                    "type": "number",
                    "initialDisplayValue": "0.05",
                    "isVisible": True,
                },
                {
                    "name": "exact_match_only",
                    "displayName": "EC Exact Match Only",
                    "type": "single-pick-vocabulary",
                    "initialDisplayValue": "Yes",
                    "isVisible": True,
                    "minSelectedCount": 1,
                    "maxSelectedCount": 1,
                },
                {
                    "name": "exclude_incomplete_ec",
                    "displayName": "Exclude Incomplete EC Numbers",
                    "type": "single-pick-vocabulary",
                    "initialDisplayValue": "No",
                    "isVisible": True,
                    "minSelectedCount": 1,
                    "maxSelectedCount": 1,
                },
            ],
        },
    }


def go_enrichment_form_response() -> dict:
    """GET .../analysis-types/go-enrichment -- form metadata.

    WDK type strings (from ``EnumParamFormatter.getParamType()``):
    - ``"single-pick-vocabulary"`` / ``"multi-pick-vocabulary"`` for enum/vocab
    - ``"number"`` for NumberParam
    """
    return {
        "searchData": {
            "name": "go-enrichment",
            "displayName": "Gene Ontology Enrichment",
            "parameters": [
                {
                    "name": "goAssociationsOntologies",
                    "displayName": "Ontology",
                    "type": "single-pick-vocabulary",
                    "initialDisplayValue": "Biological Process",
                    "isVisible": True,
                    "minSelectedCount": 1,
                    "maxSelectedCount": 1,
                },
                {
                    "name": "goEvidenceCodes",
                    "displayName": "Evidence Codes",
                    "type": "multi-pick-vocabulary",
                    "initialDisplayValue": '["Computed","Curated"]',
                    "isVisible": True,
                    "minSelectedCount": 1,
                    "maxSelectedCount": -1,
                },
                {
                    "name": "pValueCutoff",
                    "displayName": "P-value cutoff",
                    "type": "number",
                    "initialDisplayValue": "0.05",
                    "isVisible": True,
                },
                {
                    "name": "organism",
                    "displayName": "Organism",
                    "type": "single-pick-vocabulary",
                    "initialDisplayValue": "Plasmodium falciparum 3D7",
                    "isVisible": True,
                    "minSelectedCount": 1,
                    "maxSelectedCount": 1,
                },
            ],
        },
    }


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
