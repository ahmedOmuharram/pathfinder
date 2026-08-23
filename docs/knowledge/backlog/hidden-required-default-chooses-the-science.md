---
type: Backlog Item
title: 219 of the 237 hidden required defaults are still unmeasured, because a visible parameter blocks the search first
description: The sweep now exists and runs nightly. One search whose published defaults all resolve returns zero rows. The rest are blocked by a visible parameter whose own default WDK refuses, or by a 500.
tags: [wdk-alignment, parameters, silent-zero, site-model, measurement]
generated: { by: claude-code/opus-5, at: 2026-08-14T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-22T00:00:00Z }
status: stable
---

# What the sweep measured

`apps/api/src/pathfinder/tests/live/test_wdk_hidden_defaults.py` runs every transcript
search that carries a hidden required parameter with a published default, binding **every**
required parameter from its own `initialDisplayValue`, and reads `totalCount`. It is part
of the nightly lane, it is resumable, and it writes `wdk-hidden-defaults.json`.

Run against plasmodb.org on 2026-08-22:

| | count |
|---|---|
| transcript searches listed | **359** (325 on 2026-08-10) |
| carrying at least one hidden required default | **237** (182 on 2026-08-14) |
| answered 200 | 19 |
| **answered 200 with zero rows** | **1** |
| refused 422 at `RUNNABLE` | 158 |
| answered 500 | 58 |
| never answered (read timeout) | 1 |
| unmeasurable - a required parameter publishes no default | 1 |

The one search whose published defaults all resolve and which returns nothing is
`GenesByRNASeqpfal3D7_Lee_Gambian_ebi_rnaSeq_RSRCWGCNAModules`, whose hidden required
parameters are `eda_dataset_id` and `wgcnaDataset`. The other 18 returned between 14 and
several thousand genes.

**Not one of the 158 refusals names a hidden parameter.** Every parameter WDK named in
`byKey` is visible: `samples_percentile_generic` (77), `samples_fc_ref_generic` (75),
`samples_fc_comp_generic` (75), `ismTypes` (3), `text_search_organism` (2), `organism` (1).
The refusals are the visible half of
[WDK-PARAM-010](../wdk/rules/parameters-and-vocabularies.md): a published default is an
example and is not itself a valid value. No hidden default was refused by WDK.

The parameters, by what the sweep could say about them:

| outcome | parameters |
|---|---|
| cleared - a search using it returned rows | `eda_dataset_id` (6), `ProfileScaleFactor` (4), `ProfileMinPoints` (4), `geneListDataset` (4), `eda_sample_table_suffix` (2), `profileset_generic` (1), `WebServicesPath` (1), `protein_coding_only` (1) |
| returned zero | `eda_dataset_id` (1), `wgcnaDataset` (1) |
| still unmeasured | `channel` (75), `eda_dataset_id` (57), `dataset_url` (56), `hard_floor` (19), `protein_coding_only` (4), `long_read_datasets` (3), `document_type` (2), `profileset_generic` (2), `eda_sample_table_suffix` (1), `profile_pattern` (1), `BlastRecordClass` (1) |

The enumeration itself has drifted since 2026-08-14: `eda_dataset_id` (64) and four other
parameters are new, and `metadata_datasets` and `phenotypeScoreDataset` are gone. The
nightly lane now records the count on every run, so the next drift is dated rather than
rediscovered.

# What is left

**The two biggest parameters are still unmeasured**, and for the same reason: `channel`
(75 searches) and `dataset_url` (56) sit on microarray and RNA-seq searches whose visible
`samples_*` parameters have no usable default. Measuring them needs a plausible value per
search rather than a published one, which is a per-search job the sweep deliberately does
not guess at.

Two smaller questions the run raised:

- **58 searches answer 500** when every published default is bound. That is a WDK failure
  rather than an empty result, and nothing here distinguishes "the defaults are bad" from
  "this search is broken today". The nightly artifact names them.
- `profile_pattern` remains unmeasured by this sweep and does not need to be:
  `GenesByOrthologPattern` derives its pattern from the two species lists
  ([the two lists are the proposal](../decisions/phyletic-lists-are-the-proposal.md)), so
  the fill never reaches it.

# Anchor

`domain/parameters/specs.py:fill_hidden_required_defaults`, its two call sites in
`services/catalog/param_validation.py`, and
`services/catalog/param_dag.py:_is_free_text_query`. The sweep is
`tests/live/test_wdk_hidden_defaults.py`; run it with `yarn wdk:live`.

Done when the searches carrying `channel` and `dataset_url` are measured with values a
researcher would use, or that measurement is judged not worth its cost and this item is
closed by that ruling.
