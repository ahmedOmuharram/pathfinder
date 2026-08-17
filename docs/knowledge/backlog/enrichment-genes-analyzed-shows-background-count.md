---
type: Backlog Item
title: The enrichment summary "N genes analyzed" shows a term's background count, not the size of the analyzed gene set
description: A 46-gene set produced "83 significant terms - 217 genes analyzed" in the Workbench; 217 is the backgroundCount of the top term (proteolysis). derive_total_analyzed divides a term's result-gene count by the wire's percentInResult, and that percentage is result-over-background on the wire, so the formula returns the background count.
tags: [investigation, ui-run, enrichment, wdk-alignment, workbench]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB Workbench)

**What I did.** Opened the gene set "Plasmodium Gametocyte Proteolysis Genes" (46 genes,
source strategy, WDK step 440117143), expanded Enrichment Analysis with GO:BP, GO:MF,
GO:CC, Pathway, Word selected, clicked Run Enrichment.

**What I got.** Header: "GO: Biological Process 83 - GO: Molecular Function 65 - GO:
Cellular Component 55", then "83 significant terms - **217 genes analyzed**".
`POST /api/v1/gene-sets/a55fb36d.../enrich` returned for `go_process` a first term
`GO:0006508 proteolysis, geneCount 46, backgroundCount 217, foldEnrichment 20.65`.
`GET /api/v1/gene-sets/a55fb36d...` has `geneCount 46`, 46 ids.

**Why that is wrong.** The number a researcher reads as "how many of my genes went into
this test" is a different quantity (the genome-wide count of the top term). For a set where
the top term is broad it can be thousands, which reads as a broken input.

**Why it happens.** `services/enrichment/parser.py:derive_total_analyzed` computes
`round(result_genes * 100 / percent_in_result)` for the row with the most result genes,
assuming `percentInResult` is result_genes / input_size. Measured: 46 * 100 / 217 = 21.2,
so on the wire the percentage is result_genes / bgd_genes. The input size is already
known to the caller (the gene set's `geneCount`, or the step's estimated size); WDK does not
need to be asked for it.

**Fix (to decide).** Set `total_genes_analyzed` from the gene set (or step) size and drop
the derivation; if the derived value is kept anywhere, rename it to what it is. Verify the
column semantics against the GoEnrichmentPlugin source and record it under WDK-ANS-007
(`docs/knowledge/wdk/rules/searches-and-answers.md`).

**What you would get.** "83 significant terms - 46 genes analyzed".
