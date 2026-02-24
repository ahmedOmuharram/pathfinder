"""Gene result building for lookup responses."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.platform.types import JSONObject

DEFAULT_GENE_ATTRIBUTES = [
    "primary_key",
    "gene_source_id",
    "gene_name",
    "gene_product",
    "gene_type",
    "organism",
    "gene_location_text",
    "gene_previous_ids",
]


def build_gene_result(
    *,
    gene_id: str,
    display_name: str = "",
    organism: str = "",
    product: str = "",
    gene_name: str = "",
    gene_type: str = "",
    location: str = "",
    previous_ids: str = "",
    matched_fields: list[str] | None = None,
) -> JSONObject:
    """Build a standardised gene result dict.

    All gene results -- whether from site-search or WDK -- are funnelled
    through this builder so the shape is always consistent.
    """
    result: dict[str, object] = {
        "geneId": gene_id,
        "displayName": display_name or product or gene_id,
        "organism": organism,
        "product": product,
        "geneName": gene_name,
        "geneType": gene_type,
        "location": location,
    }
    if previous_ids:
        result["previousIds"] = previous_ids
    if matched_fields is not None:
        result["matchedFields"] = matched_fields
    return cast(JSONObject, result)
