---
type: Backlog Item
title: GenesByOrthologPattern's vocabulary fails validation, and the failure is reported as "Search not found" with the search in its own did-you-mean list
description: WDKVocabTerm models a vocabulary entry as (term, display, null); live plasmodb sends a parent term in the third slot, so the search's parameters fail with 1802 validation errors. The scan that catches the failure reports the search as missing, listing that same search as a suggestion.
tags: [wdk-alignment, parameters, vocabulary, error-messages, mcp]
generated: { by: claude-code/opus-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-25T00:00:00Z }
status: stable
---

# What I did

Called `lookup_phyletic_codes` over the served MCP endpoint against
plasmodb, twice, with the arguments a conformance run uses:

```
{"site_id": "plasmodb", "query": "falciparum"}
```

Then called the read underneath it directly in the api container:

```
get_search_details(SearchContext("plasmodb", "transcript", "GenesByOrthologPattern"), expand_params=True)
```

# What I got

The tool answered in 1.39 s and 2.45 s with the same error both times:

```
Failed to look up phyletic codes: Search not found: Search not found:
GenesByOrthologPattern. Did you mean: ['GenesByOrthologPattern',
'GenesByOrthologs', 'Gene...
```

The search it says is not found is the first suggestion in its own
did-you-mean list. The read underneath names the real cause:

```
DataParsingError Data parsing failed: Unexpected WDK search response for
transcript/GenesByOrthologPattern: 1802 validation errors for WDKSearchResponse
searchData.parameters.3.multi-pick-vocabulary.vocabulary.list[WDKVocabTerm].1.2
  Input should be None [type=none_required, input_value='BACT', input_type=str]
```

# Why that's wrong

`lookup_phyletic_codes` is the only way to find the species and clade codes
`GenesByOrthologPattern` accepts, so a researcher asking for genes present in
one clade and absent in another gets a refusal that names no cause and points
at the search they already asked for. `get_search_overview` on the same search
fails the same way, so the parameters cannot be read by any route. The message
also teaches the model that the search does not exist, so a retry picks a
different search and answers a different question.

# Why it happens

`WDKVocabTerm` in `apps/api/src/pathfinder/domain/parameters/wdk_vocab.py` is
`RootModel[tuple[str, str, None]]`: it requires the third element of a
vocabulary entry to be null. Live WDK puts the parent term there for a nested
vocabulary, which is what a phyletic pattern is. The parse fails, and
`_scan_record_types_for_search` in
`apps/api/src/pathfinder/services/catalog/param_discovery.py` swallows the
`AppError` into `response = None`, which reaches the "Search not found" branch
with the search still in the available list.

# Fix

Two changes, in this order.

1. `WDKVocabTerm` accepts `tuple[str, str, str | None]` and exposes the third
   element as the parent term, verified against the vocabulary live WDK sends
   for `GenesByOrthologPattern`. `phyletic_tree_of` already walks parents, so
   check whether it reads them from `indent` today and reconcile.
2. `_scan_record_types_for_search` stops reporting a parse failure as a missing
   search: when the search IS in the record type's list and reading it failed,
   the error names the read that failed, not the name that was found.

# What you'd get

`lookup_phyletic_codes(site_id="plasmodb", query="falciparum")` answers with the
matching species codes. A future parse failure says which read failed, and a
search that is genuinely absent keeps the did-you-mean list it deserves - with
itself no longer in it.
