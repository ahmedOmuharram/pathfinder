---
type: Backlog Item
title: The generic and the per-dataset EDA subset searches count different genes for the same filter
description: On plasmodb.org on 2026-08-28 the generic search GenesByEdaSubset with eda_dataset_id DS_53f554ec6a and the one-filter spec Species = P. berghei counted 5556 genes (WDK strategy 330555673, created by the batch-3 live end-to-end lane), while the per-dataset search GenesByPhenotypeEdaSubset_PlasmoDB_Rod_Mal_Phenotype_RSRC with the identical spec counted 5602 on 2026-08-27 (eda-wdk-bridge.md). Both go through GeneEdaSubsetPlugin. Not reconciled - a date difference, a query-level organism scope, or a WDK cache could explain it, and PathFinder exports through the generic search.
tags: [eda, wdk, bridge, counts, investigation]
generated: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: stable
---

**What I did.** Ran the same one-filter analysis spec through two searches on
plasmodb.org: the per-dataset `GenesByPhenotypeEdaSubset_PlasmoDB_Rod_Mal_Phenotype_RSRC`
on 2026-08-27 through the answer API, and the generic `GenesByEdaSubset` with
`eda_dataset_id` set to `DS_53f554ec6a` on 2026-08-28 through a real strategy
push.

**What I got.** 5602 genes on the per-dataset search; 5556 genes on the
generic search.

**Why that is wrong.** PathFinder's step export uses the generic search, so if
the two really differ for the same filter, a researcher who compares the
PathFinder step to the site's own search page sees two counts for one
question.

**Why it happens.** Unknown. Candidates: the two measurements are a day apart
(a data reload or a WDK cache); `GenesByEdaSubsetGeneric`, the per-dataset
query, and `GenesByEdaSubset` may differ in project or organism scoping in
`geneQueries.xml`; or the answer-API pagination counted transcripts and the
strategy counted genes.

**Fix.** Run both searches on the same day with the same spec and read
`totalCount` against `displayTotalCount` on each; if they still differ, diff
the two `processQuery` definitions in `ApiCommonModel` and record the rule in
`eda-wdk-bridge.md`.

**What you would get.** One documented count per filter, and a stated reason
when the two searches legitimately differ.
