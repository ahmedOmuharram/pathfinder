"""Gene record lookup service.

Provides two complementary lookup strategies:

1. **Text search** -- uses VEuPathDB site-search (Solr) to find genes by name,
   symbol, product description, or any free text.  Results are filtered to the
   ``gene`` document type so only gene records are returned.

2. **ID resolution** -- uses the WDK stateless standard reporter endpoint
   (``POST /record-types/{rt}/searches/{search}/reports/standard``) to fetch
   metadata for a list of known gene IDs.  Useful for validating IDs or
   retrieving product names / organisms for IDs obtained from literature.

Both approaches are read-only and do not create steps or strategies.
"""

from .lookup import batch_lookup_genes_by_text, lookup_genes_by_text
from .wdk import resolve_gene_ids

__all__ = [
    "batch_lookup_genes_by_text",
    "lookup_genes_by_text",
    "resolve_gene_ids",
]
