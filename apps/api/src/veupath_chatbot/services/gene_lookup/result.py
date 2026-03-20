"""Gene result building for lookup responses."""

from dataclasses import dataclass, field
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


@dataclass
class GeneResultInput:
    """Input fields for building a standardised gene result dict."""

    gene_id: str
    display_name: str = ""
    organism: str = ""
    product: str = ""
    gene_name: str = ""
    gene_type: str = ""
    location: str = ""
    previous_ids: str = ""
    matched_fields: list[str] | None = field(default=None)


def build_gene_result(inp: GeneResultInput) -> JSONObject:
    """Build a standardised gene result dict.

    All gene results -- whether from site-search or WDK -- are funnelled
    through this builder so the shape is always consistent.
    """
    result: dict[str, object] = {
        "geneId": inp.gene_id,
        "displayName": inp.display_name or inp.product or inp.gene_id,
        "organism": inp.organism,
        "product": inp.product,
        "geneName": inp.gene_name,
        "geneType": inp.gene_type,
        "location": inp.location,
    }
    if inp.previous_ids:
        result["previousIds"] = inp.previous_ids
    if inp.matched_fields is not None:
        result["matchedFields"] = inp.matched_fields
    return cast("JSONObject", result)
