---
type: Backlog Item
title: FilterMixin is named for view filters and writes step filters, dropping columnFilters on the way
description: Every name in the filter path says viewFilters, which WDK rejects inside searchConfig; the code correctly writes filters instead, but its PUT body omits columnFilters and silently clears them.
tags: [wdk-alignment, filters, integrations, naming]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# The defect

Two separate problems in one path, one cosmetic and one not.

**The names are wrong.** `FilterMixin` in
`apps/api/src/pathfinder/integrations/veupathdb/strategy_api/filters.py` documents itself
as managing "step filters via answerSpec.viewFilters"; its methods are `list_step_filters`
and `set_step_filter`, and the client methods behind them are `get_step_view_filters` and
`update_step_view_filters` in `integrations/veupathdb/_analyses.py`. What all four
actually read and write is `searchConfig.filters`, which is correct - and the docstrings
say so, contradicting the names above them.

That matters because the three mechanisms are genuinely different and are routinely
conflated. `viewFilters` does not live in `searchConfig` at all: on 2026-08-10 a
`PUT .../search-config` carrying the key was a **400** from the JSON schema on both
plasmodb.org and toxodb.org, and WDK's own parser reads it only from the top level of a
report request body. See [WDK-FILTER-001](../wdk/rules/filters.md) and
[WDK-FILTER-003](../wdk/rules/filters.md).

**The write is lossy.** `update_step_view_filters` re-reads the step and then PUTs a body
containing only `parameters`, `filters` and `wdkWeight`. `columnFilters` is part of the
same search config - WDK parses it, persists it, echoes it, and counts it in
`estimatedSize` - so any column filter on the step is dropped by the next call to
`set_step_filter`.

# Blast radius

The lossy write **does** change a result silently. A column filter narrows the answer;
removing it widens it, the request succeeds with 204, and nothing reports that a filter
was discarded. Verified live on both sites on 2026-08-10 that a `columnFilters` entry
drives the step's counts (a `gene_product` pattern matching nothing took `totalCount`,
`displayTotalCount` and the strategy's `estimatedSize` to 0 and flipped `isFiltered` to
true), so its removal is equally consequential.

Whether it is reachable today depends on whether anything sets a column filter on a step
that later gets a `set_step_filter` call. `sync.py:_apply_step_decorations` applies
declared step filters in a loop, so two filters on one step already means the second call
re-reads a config the first call wrote. Establish that before ranking it higher.

# How to confirm

Unit level. Drive `update_step_view_filters` through the existing transport stub with a
step whose `searchConfig` carries a non-empty `columnFilters`, and assert the PUT body
still contains it. Today it does not.

# Where to look

`update_step_view_filters` in `integrations/veupathdb/_analyses.py` for the lossy body,
and `FilterMixin` in `strategy_api/filters.py` plus its callers in
`services/strategies/sync.py` for the rename. Prefer preserving the whole `searchConfig`
and replacing only the `filters` array over enumerating keys, so the next field WDK adds
does not repeat this.

Rename in the same change rather than after it: the names are what made a
`searchConfig.viewFilters` mechanism look like it existed.

# Anchor

`update_step_view_filters` in `integrations/veupathdb/_analyses.py`. Done when a step
carrying `columnFilters` still carries them after a `set_step_filter` call, a test asserts
it, and no symbol on this path is named for view filters.
