---
type: Backlog Item
title: Whether the other 181 hidden required defaults return rows is unmeasured
description: The one hidden default known to return nothing is no longer filled - GenesByOrthologPattern derives its pattern from the two species lists. Nothing has measured the other 181 searches whose hidden required parameters are still filled from initialDisplayValue.
tags: [wdk-alignment, parameters, silent-zero, site-model, measurement]
generated: { by: claude-code/opus-5, at: 2026-08-14T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# What closed

`apps/api/src/pathfinder/domain/parameters/specs.py:fill_hidden_required_defaults`
supplies any parameter that is not visible, is not `allowEmptyValue`, is absent from the
caller's values, and has an `initialDisplayValue`. The premise is sound and unchanged: a
hidden parameter stays required and stays default-filled
([WDK-PARAM-011](../wdk/rules/parameters-and-vocabularies.md)), and something must supply
these values.

**The one search where the filled value was known to be wrong no longer reaches the
fill.** `GenesByOrthologPattern.profile_pattern` is derived from the two species lists the
model proposes and written together with them
([the two lists are the proposal](../decisions/phyletic-lists-are-the-proposal.md),
[WDK-SITE-006](../wdk/rules/site-model-params.md)). Live on plasmodb.org on 2026-08-17
with `organism` at *P. falciparum* 3D7, the derived `%hsap:N%pfal:Y%` returns **3,347**
genes where the published default `hsap=1T` returns **0**. On the gold corpus the same
change moved the propose arm from 285 exact / 18 wrong to **288 exact / 15 wrong** over
332 parameters, and both gold `GenesByOrthologPattern` steps now score exact on the pattern
and on both lists.

The reporting half closed earlier and stays. `specs.filled_hidden_defaults` names the
parameters a fill supplies, `validate_parameters` merges them into
`ValidatedParams.substituted`, and `frame_spec` folds them into the criterion's `defaulted`
list, so a filled hidden value is one the model is told it did not choose, on the same
footing as a value WDK substituted
([WDK-PARAM-008](../wdk/rules/parameters-and-vocabularies.md)).

# What is left, and why it is still worth carrying

**The enumeration, measured on plasmodb.org on 2026-08-14.** Every transcript search:
**182 of 325 carry at least one hidden required parameter** with a published default. The
parameters, by how many searches ask for them:

| count | parameter |
|---|---|
| 73 | `channel` |
| 54 | `dataset_url` |
| 19 | `hard_floor` |
| 5 each | `metadata_datasets`, `protein_coding_only` |
| 4 each | `phenotypeScoreDataset`, `ProfileScaleFactor`, `ProfileMinPoints` |
| 1 | `profile_pattern` |

One of those 182 searches is now supplied by the caller. **Nothing has measured whether the
defaults on the other 181 return rows.** Nothing at any layer promises they do: the
declared default is stored by a setter whose javadoc promises validation and whose body
assigns, and valid has never meant "returns rows"
([WDK-PARAM-010](../wdk/rules/parameters-and-vocabularies.md)).

**The cheap proxy has already been run and does not settle it.** The tell on
`profile_pattern` was that its default is quoted verbatim in its own `<help>`, which reads
`Example: 'hsap=1T'` and nothing else. Searching every hidden required parameter for a
default that appears in its own help text finds four:

| parameter | searches | default | help |
|---|---|---|---|
| `channel` | 73 | `Channel 1` | prose describing two-channel experiments |
| `hard_floor` | 16 | `0` | prose describing the read floor |
| `ReadFrequencyPercent` | 1 | `0%` | prose describing isolate reads |
| **`profile_pattern`** | **1** | `hsap=1T` | **`Example: 'hsap=1T'`** |

The first three mention their default while describing what it means, which is a parameter
documenting itself rather than an example standing in for a value. That is a reading of
prose, not a measurement, and a parameter can be a poor default without being an example.

**One consequence is written into the code as a belief.**
`services/catalog/param_dag.py:_is_free_text_query` excludes hidden parameters from the
free-text guard, with the comment "Hidden params and numeric bounds carry real defaults and
are excluded." The numeric half is settled
([numeric-default-is-not-an-example](../decisions/numeric-default-is-not-an-example.md)).
The hidden half now has no known counterexample and no evidence either, which is exactly
the state this item records.

# The check that settles it

For each of the 182 searches, run it with only its visible required parameters bound and
read `totalCount`. A zero is a candidate; a non-zero clears that parameter. Most of these
searches need a real organism or dataset before they run at all, so this is a per-search
job rather than one sweep, which is why it has not been done.

# Anchor

`domain/parameters/specs.py:fill_hidden_required_defaults`, its two call sites in
`services/catalog/param_validation.py`, and `services/catalog/param_dag.py:_is_free_text_query`.
Coverage is `tests/unit/domain/parameters/test_hidden_required_defaults.py`, which asserts
the fill happens, and `tests/unit/domain/parameters/test_hidden_fill_is_reported.py`, which
asserts it is reported. Neither can assert that a filled value returns rows; only the live
sweep above can.

Done when the searches whose hidden defaults return nothing are named, or the sweep is
judged not worth its cost and this item is closed by that ruling.
