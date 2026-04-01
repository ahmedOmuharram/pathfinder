"""AI tool wrappers for catalog/discovery — single layer, WDK-direct.

Every tool operates on the session's site. The model never passes site_id.
"""

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.ai.tools.query_validation import (
    search_query_error,
)
from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.factory import (
    get_strategy_api,
    get_wdk_client,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WdkParams, encode_wdk_params
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services import catalog
from veupath_chatbot.services.catalog.param_formatting import format_typed_param
from veupath_chatbot.services.catalog.public_strategy_search import (
    rank_public_strategies,
)
from veupath_chatbot.services.catalog.searches import find_record_type_for_search

from veupath_chatbot.integrations.veupathdb.wdk_parameters import WDKBaseParameter

logger = get_logger(__name__)

_DEFAULT_RECORD_TYPE = "transcript"


def _filter_vocab(param: WDKBaseParameter, query: str) -> WDKBaseParameter:
    """Return a copy of the parameter with vocabulary filtered by query.

    For tree vocabularies (``{data, children}`` dicts), walks the tree
    and keeps only subtrees where any node's ``data.term`` or
    ``data.display`` contains the query (case-insensitive).

    For flat vocabularies (lists), keeps entries matching the query.

    Returns a new parameter via ``model_copy`` since WDK parameter
    models are frozen.
    """
    if param.vocabulary is None:
        return param

    q = query.lower()

    match param.vocabulary:
        case dict() as tree:
            pruned = _prune_tree(tree, q)
            return param.model_copy(update={"vocabulary": pruned or tree})
        case list() as flat:
            filtered = [
                entry for entry in flat
                if q in str(entry).lower()
            ]
            return param.model_copy(update={"vocabulary": filtered})

    return param


def _prune_tree(node: JSONObject, query: str) -> JSONObject | None:
    """Recursively prune a vocab tree, keeping only branches matching query.

    A node is kept if its own term/display matches, or if any descendant
    matches.  Returns None if the entire subtree should be pruned.
    """
    data = node.get("data", {})
    data_dict = data if isinstance(data, dict) else {}
    term = str(data_dict.get("term", "")).lower()
    display = str(data_dict.get("display", "")).lower()
    self_matches = query in term or query in display

    children_raw = node.get("children", [])
    children = children_raw if isinstance(children_raw, list) else []

    kept_children = []
    for child in children:
        if isinstance(child, dict):
            pruned = _prune_tree(child, query)
            if pruned is not None:
                kept_children.append(pruned)

    if not self_matches and not kept_children:
        return None

    return {"data": data, "children": kept_children}


async def _resolve_record_type(
    site_id: str, search_name: str, record_type: str | None
) -> str:
    """Resolve record type from the cached catalog, falling back to 'transcript'."""
    ctx = SearchContext(site_id, record_type or _DEFAULT_RECORD_TYPE, search_name)
    return await find_record_type_for_search(ctx)


# Universal searches present on ALL 12 VEuPathDB sites.  Appended to every
# search_for_searches result so the model always sees them — regardless of
# how well the retrieval layer scored them.
_UNIVERSAL_SEARCHES: list[dict[str, str | float]] = [
    {
        "name": "GenesByText",
        "displayName": "Text (product name, notes, etc.)",
        "description": (
            "Find genes with a text search against their product name, "
            "notes, GO, EC, Domains, NRDB, or metabolic pathways."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByGoTerm",
        "displayName": "GO Term",
        "description": (
            "Find genes based on the Gene Ontology (GO) Term(s) or ID(s) "
            "assigned to them."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesWithSignalPeptide",
        "displayName": "Predicted Signal Peptide",
        "description": (
            "Find genes that are predicted to encode a secretory signal "
            "peptide containing protein."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByTransmembraneDomains",
        "displayName": "Transmembrane Domain Count",
        "description": (
            "Find genes whose protein products are predicted to have "
            "transmembrane domains numbering within a range that you specify."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByExonCount",
        "displayName": "Exon Count",
        "description": (
            "Find genes that have exons numbering within a range that you specify."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByInterproDomain",
        "displayName": "InterPro Domain",
        "description": (
            "Find genes containing a specified protein domain from the "
            "InterPro database (includes CATH, CDD, HAMAP, PANTHER, Pfam, "
            "PIRSF, PRINTS, PROSITE, SFLD, SMART, SUPERFAMILY, TIGRFAMs)."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByMotifSearch",
        "displayName": "Protein Motif Pattern",
        "description": (
            "Find genes whose protein product contains a regex motif "
            "pattern that you specify."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByOrthologs",
        "displayName": "Transform by Orthology",
        "description": (
            "Find orthologs or paralogs of genes in a search result. "
            "Use via list_transforms."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByRNASeqEvidence",
        "displayName": "RNA-Seq Evidence",
        "description": (
            "Find genes based on their expression levels quantified by RNA-Seq."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByMassSpec",
        "displayName": "Mass Spec. Evidence",
        "description": (
            "Find genes that have evidence for protein-level expression "
            "from mass spectrometry-based proteomics."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesBySimilarity",
        "displayName": "BLAST",
        "description": (
            "Find genes that have BLAST similarity to your input sequence."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByLocation",
        "displayName": "Genomic Location",
        "description": (
            "Find genes within a given genomic region (chromosome, scaffold, "
            "supercontig)."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesByTaxon",
        "displayName": "Organism",
        "description": "Find all genes from one or more species/organism.",
        "category": "universal",
        "relevance": "always-available",
    },
    {
        "name": "GenesBySpanLogic",
        "displayName": "Genes by Relative Location",
        "description": (
            "Genomic co-location: find genes near other genomic features "
            "on the same chromosome (e.g. genes within N bp of SNPs, "
            "motifs, or other gene results). Use with COLOCATE operator."
        ),
        "category": "universal",
        "relevance": "always-available",
    },
]


class CatalogTools:
    """Tools for exploring VEuPathDB catalog.

    Constructed with the session's ``site_id`` — every tool uses it implicitly.
    """

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id

    # -- Sites & record types --------------------------------------------------

    @ai_function()
    async def list_sites(self) -> list[dict[str, object]]:
        """List all available VEuPathDB sites."""
        sites = await catalog.list_sites()
        return [
            s.model_dump(by_alias=True, exclude_none=True, mode="json") for s in sites
        ]

    @ai_function()
    async def get_record_types(self) -> list[dict[str, str]]:
        """List available record types for this site."""
        record_types = await catalog.get_record_types(self.site_id)
        return [
            {
                "name": rt.name,
                "displayName": rt.display_name,
                "description": rt.description,
            }
            for rt in record_types
        ]

    # -- Search discovery ------------------------------------------------------

    @ai_function()
    async def search_for_searches(
        self,
        query: Annotated[
            str,
            AIParam(
                desc=(
                    "Descriptive natural language query about what you're looking for. "
                    "Must include 5+ specific keywords — be as descriptive as possible. "
                    "Example: 'gametocyte RNA-Seq differential expression DESeq analysis'"
                )
            ),
        ],
        record_type: Annotated[
            str | None,
            AIParam(
                desc="Filter to a specific record type (e.g., 'transcript'). Omit for all."
            ),
        ] = None,
        keywords: Annotated[
            list[str] | None,
            AIParam(
                desc=(
                    "Optional exact identifiers to match against search names (urlSegment). "
                    "These get massive score boost. Extract from dataset names, search "
                    "name fragments, or organism codes mentioned in the user's request. "
                    "Example: ['Su_strand_specific', 'Percentile', 'pfal3D7']"
                )
            ),
        ] = None,
        category: Annotated[
            str | None,
            AIParam(
                desc=(
                    "Filter to a specific search subcategory from the site ontology. "
                    "Pick the most specific category matching the user's intent:\n"
                    "  - 'searchCategory-transcriptomics-differential-expression': DESeq statistical tests\n"
                    "  - 'searchCategory-transcriptomics-fold-change': fold change threshold\n"
                    "  - 'searchCategory-transcriptomics-percentile': expression percentile\n"
                    "  - 'searchCategory-transcriptomics-sense-antisense': strand-specific\n"
                    "  - 'searchCategory-transcriptomics-direct-comparison': microarray direct comparison\n"
                    "  - 'searchCategory-proteomics-direct-comparison': proteomics comparison\n"
                    "  - 'searchCategory-phenotype-curated': curated phenotype data\n"
                    "  - 'searchCategory-chipchip': ChIP-chip/ChIP-seq epigenomics\n"
                    "  - 'searchCategory-coexpression': co-expression networks\n"
                    "  - None: no filtering (universal searches + all categories)"
                )
            ),
        ] = None,
        limit: Annotated[int, AIParam(desc="Max results to return.")] = 20,
    ) -> list[dict[str, str | float]]:
        """Find WDK searches by description and/or keywords.

        Returns a ranked list with name, displayName, description, category,
        what the search returns, and a relevance score (0-1, higher is better).
        Prefer searches with higher relevance scores.
        """
        kw = keywords or []
        err = search_query_error(query, has_keywords=bool(kw))
        if err is not None:
            return [err]
        matches = await catalog.search_for_searches(
            self.site_id,
            record_type=record_type,
            query=query,
            keywords=kw,
            category=category,
            limit=limit,
        )
        results: list[dict[str, str | float]] = [m.to_dict() for m in matches]

        # Always append universal searches the model should know about,
        # skipping any that already appeared in the ranked results.
        seen = {str(r["name"]) for r in results}
        results.extend(u for u in _UNIVERSAL_SEARCHES if str(u["name"]) not in seen)

        return results

    @ai_function()
    async def browse_search_categories(
        self,
        record_type: Annotated[
            str,
            AIParam(desc="Record type (e.g., 'transcript'). Defaults to transcript."),
        ] = "transcript",
    ) -> list[dict[str, str | int | list[str]]]:
        """Browse available search categories and their example searches.

        Call this BEFORE search_for_searches to see what categories and search
        names exist on this site.  Returns categories grouped by the site's
        ontology, each with a count and up to 5 example display names.
        Use the category key as the 'category' parameter in search_for_searches.
        Use the example display names to formulate better search queries.
        """
        return await catalog.browse_search_categories(self.site_id, record_type)

    @ai_function()
    async def list_searches(
        self,
        record_type: Annotated[
            str, AIParam(desc="Record type (e.g., 'gene', 'transcript')")
        ],
    ) -> list[dict[str, str]]:
        """List all search names for a record type (names only, no descriptions).

        Use search_for_searches first for targeted discovery with descriptions.
        """
        return await catalog.list_searches(self.site_id, record_type)

    @ai_function()
    async def list_transforms(
        self,
        record_type: Annotated[str, AIParam(desc="Record type (e.g., 'transcript')")],
    ) -> list[dict[str, str]]:
        """List available transform and combine operations (with descriptions).

        Returns searches that chain onto a previous step's results — such as
        ortholog transforms, weight filters, span logic, and boolean combines.
        """
        return await catalog.list_transforms(self.site_id, record_type)

    # -- Search details --------------------------------------------------------

    @ai_function()
    async def get_search_parameters(
        self,
        search_name: Annotated[str, AIParam(desc="Search name")],
        record_type: Annotated[
            str | None,
            AIParam(desc="Record type (e.g., 'transcript'). Auto-resolved if omitted."),
        ] = None,
    ) -> JSONObject:
        """Get full details for a specific search: description, parameters, and valid values."""
        rt = await _resolve_record_type(self.site_id, search_name, record_type)
        return await catalog.get_search_parameters_tool(
            SearchContext(self.site_id, rt, search_name)
        )

    @ai_function()
    async def get_dependent_vocab(
        self,
        search_name: Annotated[str, AIParam(desc="Search name")],
        param_name: Annotated[str, AIParam(desc="Dependent parameter name to refresh")],
        record_type: Annotated[
            str | None,
            AIParam(desc="Record type. Auto-resolved if omitted."),
        ] = None,
        context_values: Annotated[
            WdkParams | None,
            AIParam(desc="Current contextParamValues (paramName -> value)"),
        ] = None,
        query: Annotated[
            str | None,
            AIParam(
                desc="Optional search filter for large vocabularies. "
                "Only returns entries whose label contains this substring (case-insensitive). "
                "Use when the vocabulary is truncated and you need specific entries "
                "(e.g. query='cruzi' to find T. cruzi mass spec assays)."
            ),
        ] = None,
    ) -> JSONObject:
        """Get dependent vocab for a parameter.

        WDK's refreshed-dependent-params requires a changed param value.
        If context_values does not include param_name, falls back to
        expanded search details.
        """
        rt = await _resolve_record_type(self.site_id, search_name, record_type)
        ctx = context_values or {}
        has_context = any(v is not None and v != "" for v in ctx.values())

        if has_context:
            client = get_wdk_client(self.site_id)
            encoded_ctx = encode_wdk_params(ctx)
            result = await client.get_search_details_with_params(
                rt,
                search_name,
                context=encoded_ctx,
                expand_params=True,
            )
            for p in result.search_data.parameters or []:
                if p.name == param_name:
                    filtered = _filter_vocab(p, query) if query else p
                    return format_typed_param(filtered, depends_on={}, controls={})
            return {"error": "param_not_found", "paramName": param_name}

        # Fallback: fetch expanded search details
        client = get_wdk_client(self.site_id)
        details = await client.get_search_details(
            rt,
            search_name,
            expand_params=True,
        )
        for p in details.search_data.parameters or []:
            if p.name == param_name:
                if query:
                    _filter_vocab(p, query)
                return format_typed_param(p, depends_on={}, controls={})
        return {"error": "param_not_found", "paramName": param_name}

    # -- Phyletic codes --------------------------------------------------------

    @ai_function()
    async def lookup_phyletic_codes(
        self,
        record_type: Annotated[str, AIParam(desc="Record type (usually 'transcript')")],
        query: Annotated[
            str,
            AIParam(
                desc=(
                    "Species or clade name to search for "
                    "(e.g., 'falciparum', 'human', 'Apicomplexa'). "
                    "Returns matching codes for use in profile_pattern."
                )
            ),
        ],
    ) -> JSONObject:
        """Look up phyletic species/group codes by name for GenesByOrthologPattern.

        Returns {code, label, leaf} triples. Use codes in profile_pattern:
        %CODE:Y% (include) or %CODE:N% (exclude).
        """
        return await catalog.lookup_phyletic_codes(self.site_id, record_type, query)

    # -- Example plans ---------------------------------------------------------

    @ai_function()
    async def search_example_plans(
        self,
        query: Annotated[
            str, AIParam(desc="User goal / query to match against public strategies")
        ],
        limit: Annotated[int, AIParam(desc="Max number of results to return")] = 3,
    ) -> list[JSONObject]:
        """Retrieve relevant public strategies from WDK matched by text relevance."""
        try:
            api = get_strategy_api(self.site_id)
            public_strategies = await api.list_public_strategies()
            return rank_public_strategies(public_strategies, query=query, limit=limit)
        except (AppError, OSError) as exc:
            logger.warning("Failed to fetch public strategies", error=str(exc))
            return []
