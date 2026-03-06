"""Gene-specific relevance scoring for text search results."""

from __future__ import annotations

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.search_rerank import (
    score_field_quality,
    score_text_match,
)

from .organism import score_organism_match

_W_GENE_ID = 100.0
_W_GENE_NAME = 40.0
_W_ORGANISM = 30.0
_W_PRODUCT = 35.0
_W_DISPLAY_NAME = 25.0
_W_FIELD_QUALITY = 20.0
_EXACT_BONUS = 80.0


def score_gene_relevance(query: str, result: JSONObject) -> float:
    """Score a gene result's relevance to *query*.

    Higher is better.  The score is an additive combination of how well
    the query matches the gene ID, gene name, organism, and product,
    plus a bonus/penalty based on which site-search fields matched.

    An extra bonus is awarded when the query exactly matches a descriptive
    field (product, displayName) so that exact hits always rank above
    incidental fuzzy overlap from shared tokens like "alpha" or "2".
    """
    gene_id = str(result.get("geneId", ""))
    gene_name = str(result.get("geneName", ""))
    display_name = str(result.get("displayName", ""))
    organism = str(result.get("organism", ""))
    product = str(result.get("product", ""))
    matched_fields = result.get("matchedFields")
    mf_list = matched_fields if isinstance(matched_fields, list) else []
    mf_list_str: list[str] = [x for x in mf_list if isinstance(x, str)]

    id_score = score_text_match(query, gene_id)
    name_score = score_text_match(query, gene_name)
    disp_score = score_text_match(query, display_name)
    prod_score = score_text_match(query, product)

    score = 0.0
    score += _W_GENE_ID * id_score
    score += _W_GENE_NAME * name_score
    score += _W_DISPLAY_NAME * disp_score
    score += _W_ORGANISM * score_organism_match(query, organism)
    score += _W_PRODUCT * prod_score
    score += _W_FIELD_QUALITY * score_field_quality(mf_list_str)

    # Exact/near-exact match bonus — ensures "alpha tubulin 2" beats
    # "casein kinase 2, alpha subunit" which only shares tokens.
    best_desc = max(prod_score, disp_score, name_score)
    if best_desc >= 0.95:
        score += _EXACT_BONUS * best_desc

    return score
