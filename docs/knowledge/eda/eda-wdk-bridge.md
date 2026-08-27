---
type: Reference
title: The EDA-WDK bridge
description: How an EDA analysis becomes a WDK step through the eda_analysis_spec parameter and the WSF gene plugins, proven live on PlasmoDB with real counts.
tags: [eda, wdk, bridge, steps, strategies, eda_analysis_spec, wsf]
generated: { by: claude-code/fable-5, at: 2026-08-27T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-27T00:00:00Z }
status: stable
---

# The EDA-WDK bridge

EDA output enters a strategy as an ordinary WDK step. There is no new WDK
concept: the whole bridge is two string parameters on ordinary gene searches,
resolved by a WSF plugin that calls the EDA service and hands WDK a gene list.
A step built this way combines, transforms, nests, and saves exactly like any
other step.

## The parameters

Defined in `ApiCommonModel/Model/lib/wdk/model/questions/params/geneParams.xml`:

- `eda_dataset_id`: a `stringParam` (or, for user datasets, a
  `flatVocabParam` over installed VDI datasets) holding the dataset id
  (`DS_xxx`). Per-dataset generated searches default it to the dataset
  presenter id and hide it.
- `eda_analysis_spec`: a multiline `stringParam` holding the JSON of an EDA
  `NewAnalysis` (see [what-eda-is.md](what-eda-is.md), Analyses). Empty is
  allowed and means "no filters": the plugin synthesizes an empty descriptor.

## The searches

In `ApiCommonModel/Model/lib/wdk/model/questions/queries/geneQueries.xml`:

- `GenesByEdaSubset` -> processQuery
  `org.apidb.apicomplexa.wsfplugin.eda.GeneEdaSubsetPlugin`: genes in the
  filtered subset. `GenesByEdaSubsetGeneric` is a third declared process query
  on the same plugin with `eda_dataset_id` hidden; it is the `queryRef` every
  per-dataset subset template uses, and the genomics-site UI routes the subset
  widget on `queryName === 'GenesByEdaSubsetGeneric'`, so the bare
  `GenesByEdaSubset` gets no EDA widget.
- `GenesByEdaVizWithCompute` -> `GeneEdaVizWithComputePlugin`: genes passing a
  compute-backed volcano visualization's thresholds, with dynamic columns
  `effectSize` and `pValue`. The bridge is volcano-only by construction: the
  plugin's `findVolcanoComputation` accepts a computation only if it carries a
  visualization of `type == "volcanoplot"` whose configuration has both
  `effectSizeThreshold` and `significanceThreshold`, and throws otherwise. So
  only `differentialexpression` and `differentialabundance` can reach a step
  this way (see [notebook-presets.md](notebook-presets.md)).
- Per-dataset searches are stamped out of `.dst` templates (`phenotype.dst`,
  `antibodyArray.dst`, `rnaSeqTemplates.dst`, `cellularLocalization.dst`) as
  `GenesByPhenotypeEdaSubset_{dataset}` and the like. `chipchip.dst` reads the
  same `eda.*` tables but stamps no EDA search: its templates feed a classic
  WDK `filterParam` and its gene query answers from
  `webready.ChIPchipTranscript_p`
  (see [genomics-and-wdk-relations.md](genomics-and-wdk-relations.md)).
- VDI user datasets route through the same plugins:
  `GenesByPhenotypeUserDataset`, `GenesByDESeqUserDataset`.

Live on PlasmoDB (2026-08-27), 68 of the transcript record type's 359 searches
declare `eda_analysis_spec`: 52 `GenesByRNASeq{dataset}DESeq`, 6 per-dataset
phenotype, 5 antibody-array, `GenesByEdaSubset`, `GenesByEdaVizWithCompute`,
`GenesByPhenotypeUserDataset`, `GenesByDESeqUserDataset`, and one
WGCNA-modules search whose SQL never reads the spec. Only 13 of the 68 have
`Eda` in their name, so an EDA-backed search is identified by the parameter,
never by the name.

## What the subset plugin does

`ApiCommonWebService/WSFPlugin/.../eda/AbstractEdaGenesPlugin.java` and
`GeneEdaSubsetPlugin.java`:

1. Parse `eda_analysis_spec`; require `studyId` in the spec to equal
   `eda_dataset_id` when both are present. Both are DATASET ids: the plugin's
   own comment reads `_datasetId = _analysisSpec.getString("studyId"); //
   misnamed; still need to look up study ID`, and its mismatch error ends
   "Note both values should be dataset IDs, not study IDs (old API)."
2. Resolve dataset -> study id via `GET {eda}/permissions`
   (`perDataset[datasetId].studyId`), which also enforces the user's access.
3. Fetch the study's entity tree and locate the entity carrying the variable
   with the reserved id `VEUPATHDB_GENE_ID`. The study must contain exactly
   one such variable, or the request fails.
4. `POST {eda}/studies/{study}/entities/{entity}/tabular` with
   `outputVariableIds: [VEUPATHDB_GENE_ID]` and the spec's
   `descriptor.subset.descriptor` filter array, `Accept:
   text/tab-separated-values`.
5. Stream the gene column into a WDK temporary table, expanding cells that
   hold JSON arrays of gene ids into one row each.
6. Join to `apidbtuning.transcriptattributes` (case-insensitive on
   `apidbtuning.geneid`) and emit transcript rows to WDK.

The plugin authenticates to EDA with the requesting user's bearer token
(`Authorization: Bearer ...`); there is no service account in the path.

## What the compute plugin adds

`GeneEdaVizWithComputePlugin` reads the spec's first computation and its first
visualization. It then:

1. `POST {eda}/computes/{computeName}?autostart=true` with {studyId, filters,
   config, derivedVariables}. Status `complete` proceeds; `queued` or
   `in-progress` throws WDK's `DelayedResultException`; `failed`, `expired`,
   `no-such-job` error out. Measured live (2026-08-27): while the job runs,
   the answer API returns **HTTP 202** with body
   `{"message":"WDK-DELAYED-RESULT","status":"accepted"}` - and the WDK
   request itself starts the compute, because the plugin posts with
   `autostart=true`. Retrying the identical request after completion returns
   the 200 answer. Full sequence: [notebook-presets.md](notebook-presets.md).
2. When complete, `POST {eda}/apps/{computeName}/visualizations/{vizName}`
   and stream the `statistics` array. The plugin uses `computeName` as the
   APP url segment, which works only because the volcano apps share their
   compute's name; apps and computes are distinct namespaces in general
   (`rankedabundance` backs the app named `abundance`).
3. Retain points passing the viz configuration's `effectSizeThreshold`,
   `significanceThreshold`, and `effectDirection` (upOnly, downOnly,
   upAndDown), and deliver genes with `effectSize` and `pValue` as dynamic
   step columns.

So the thresholds a user drags on the volcano plot ARE the search parameters;
they travel inside the analysis JSON.

## The notebook UI is only a param editor

Questions carrying the `edaNotebookType` property (values live today:
`differentialExpressionNotebook`, `wgcnaCorrelationNotebook`,
`antibodyArrayNotebook`) get their
entire question form replaced by
`genomics-site/.../questions/EdaNotebookQuestionForm.tsx` and
`EdaNotebookParameter.tsx`, which mount the EDA notebook and serialize every
notebook change back into `eda_analysis_spec` via `updateParamValue`. WDK
never knows a notebook exists; it sees a string parameter.

## Live proof (2026-08-27, plasmodb.org)

Search `GenesByPhenotypeEdaSubset_PlasmoDB_Rod_Mal_Phenotype_RSRC`
(`eda_dataset_id` default `DS_53f554ec6a`, study `STUDY_53f554ec6a`, one
entity `GENE_PHENOTYPE_DATA_ENTITY` with 13 string variables including
`VEUPATHDB_GENE_ID`), run through the plain answer API
`POST /plasmo/service/record-types/transcript/searches/{search}/reports/standard`:

- empty `eda_analysis_spec` -> `totalCount` **5810**
- one filter `{"entityId": "GENE_PHENOTYPE_DATA_ENTITY", "variableId":
  "VAR_035294d0", "type": "stringSet", "stringSet": ["P. berghei"]}` ->
  `totalCount` **5602**

Same transport PathFinder already speaks; nothing about the EDA bridge needs a
browser.
