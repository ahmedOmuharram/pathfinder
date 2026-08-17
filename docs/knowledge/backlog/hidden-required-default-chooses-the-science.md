---
type: Backlog Item
title: Filling a hidden required parameter from initialDisplayValue chooses the science on at least one search
description: fill_hidden_required_defaults is the right shape for a parameter WDK demands and the model cannot supply, but initialDisplayValue carries no guarantee - on GenesByOrthologPattern it is an expression from another site's grammar that returns zero on both sites.
tags: [agents, wdk-alignment, parameters, silent-zero, site-model]
generated: { by: claude-code/opus-5, at: 2026-08-14T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# The defect

`apps/api/src/pathfinder/domain/parameters/specs.py:fill_hidden_required_defaults` supplies
any parameter that is not visible, is not `allowEmptyValue`, is absent from the caller's
values, and has an `initialDisplayValue`. Its docstring gives the reason, and the reason is
sound: "WDK rejects a search without these params, but the model cannot set them." It is
called twice from `services/catalog/param_validation.py`.

The premise is correct. `isVisible: false` is presentation and nothing else - a hidden
parameter stays in `getRequiredParams()`, stays in the validation loop, and stays
default-filled ([WDK-PARAM-011](../wdk/rules/parameters-and-vocabularies.md)). Something
must supply these values.

The gap is what gets supplied. `initialDisplayValue` is the value the displayable spec
happens to hold, filled from a model default that WDK never validates - the setter's
javadoc promises validation and its body is a bare assignment, and the RelaxNG schema types
the attribute as free text ([WDK-PARAM-010](../wdk/rules/parameters-and-vocabularies.md)).
Nothing at any layer promises that a default returns rows. Validity means "passes the
type's `validateValue`", which for a `string` is number-parseability, a regex if one is
declared, and a length cap.

# Where it bites, measurably

`GenesByOrthologPattern.profile_pattern` is hidden, required, and publishes
`initialDisplayValue: "hsap=1T"` on plasmodb.org and toxodb.org. That string is a valid
expression in **OrthoMCL's** `phyletic_expression` grammar, not a `profile_pattern`, and on
both sites it returns `totalCount` **0** with HTTP 200
([WDK-SITE-003](../wdk/rules/site-model-params.md)).

So on this search the fill does not merely pick a placeholder. It chooses the phyletic
criterion, chooses it wrong, and the wrongness is a clean empty answer rather than an
error.

# What a researcher experiences

They ask for genes with some conservation pattern. The agent resolves a
`GenesByOrthologPattern` step. Nothing asks them about `profile_pattern`, because it is
hidden and therefore not a slot the model is allowed to fill. The step is built, is valid,
runs, and returns zero genes. If the agent goes on to intersect that step with anything,
the whole strategy is empty, and the explanation offered will be about the *other*
criteria, because the phyletic one never appeared in the conversation.

The parameter that decided the answer is the one nobody saw.

# There is a second, quieter instance of the same belief

`services/catalog/param_dag.py:_is_free_text_query` excludes hidden parameters from the
free-text guard, with the comment "Hidden params and numeric bounds carry real defaults and
are excluded." Numeric bounds do carry real defaults, and that half is settled
([numeric-default-is-not-an-example](../decisions/numeric-default-is-not-an-example.md)).
The hidden half is the claim this item disputes: `profile_pattern` is hidden and its
default is an example - it is literally the same string as the `<help>` text, `Example:
'hsap=1T'`. Whatever is decided about the fill has to be decided about this guard in the
same change, or the two will disagree.

# What is *not* being asked for

Not "stop filling hidden required parameters". WDK requires them, the model cannot supply
them, and removing the fill turns a silent zero into a 422 on every such search. The fill
is the right shape.

# Half of it is measured, and half is now reported

**The enumeration.** Every transcript search on plasmodb.org, 2026-08-14:
**182 of 325 carry at least one hidden required parameter** with a published
default. The parameters, by how many searches ask for them:

| count | parameter |
|---|---|
| 73 | `channel` |
| 54 | `dataset_url` |
| 19 | `hard_floor` |
| 5 each | `metadata_datasets`, `protein_coding_only` |
| 4 each | `phenotypeScoreDataset`, `ProfileScaleFactor`, `ProfileMinPoints` |
| 1 | `profile_pattern` |

So the fill is ordinary rather than exotic, and `profile_pattern` - the one
known to return nothing ([WDK-SITE-003](../wdk/rules/site-model-params.md)) - is
one search out of 325. Five searches errored and are not counted.

**The second question is answered rather than deferred.**
`specs.filled_hidden_defaults` names the parameters a fill supplies, and
`validate_parameters` merges them into `ValidatedParams.substituted`, which
`frame_spec` already folds into the criterion's `defaulted` list. A filled
hidden parameter is now a value the model is told it did not choose, on the same
footing as one WDK substituted ([WDK-PARAM-008](../wdk/rules/parameters-and-vocabularies.md)).

# How many of those defaults are examples rather than values

The cheap version of the second question, run over the same 325 searches. The
tell on `profile_pattern` is that its default is quoted verbatim in its own
`<help>`, which is `Example: 'hsap=1T'` and nothing else. Searching every hidden
required parameter for a default that appears in its own help text finds **four**,
and only one of them is that shape:

| parameter | searches | default | help |
|---|---|---|---|
| `channel` | 73 | `Channel 1` | prose describing two-channel experiments |
| `hard_floor` | 16 | `0` | prose describing the read floor |
| `ReadFrequencyPercent` | 1 | `0%` | prose describing isolate reads |
| **`profile_pattern`** | **1** | `hsap=1T` | **`Example: 'hsap=1T'`** |

The first three mention their default while describing what it means, which is
a parameter documenting itself. The fourth has no description at all - the help
*is* the example, and the example is the default.

So the failure this item is named for is, on this site, **one parameter out of
the 182 searches that fill something**. That does not make the fill safe: nothing
in the model promises any of the other 181 return rows, and a parameter can be a
poor default without being an example. It does mean the item is a known
single instance plus an unquantified tail, rather than a systemic hazard.

# What is still open

Whether each of those 182 defaults returns rows. Answering it means running each
search with only its visible required parameters bound, and most need a real
organism or dataset first, so it is a per-search job rather than one sweep. The
reporting above is what makes the unanswered half survivable: a filled value is
visible, so a zero can be attributed rather than guessed at.

# The check that settles the rest

Two questions, both cheap.

1. **How many hidden required parameters are there, and how many have a default that
   returns nothing?** Enumerate every transcript search on plasmodb.org, collect the
   parameters with `isVisible: false` and `allowEmptyValue: false`, and count them. Then,
   for each search that has one, run the search once with only the visible required
   parameters bound and read `totalCount`. A zero is a candidate; a non-zero clears that
   parameter. This turns "at least one" into a number and decides whether the answer is a
   per-parameter override or a general policy.
2. **Is a filled hidden parameter distinguishable after the fact?** Today the filled value
   is indistinguishable from a value the user chose, in the step and in anything reading
   the step back. At minimum the fill should be recorded as a substitution, which is
   machinery that already exists for WDK's own substitutions
   ([WDK-PARAM-008](../wdk/rules/parameters-and-vocabularies.md), and
   `services/catalog/test_wdk_substitution.py`).

# Measured again on 2026-08-17, and the same search is now the largest error source

On the gold corpus, with the model proposing every visible parameter from the
parameter sheet ([one proposer, one validator](../decisions/one-proposer-one-validator.md)),
`GenesByOrthologPattern` is **7 of the 18 wrong values** across 70 steps, and six
of the seven are structural rather than model error:

- **2 rows are `profile_pattern` itself.** It is hidden, so it is not on the
  sheet, so the model cannot propose it and the fill supplies `hsap=1T` while
  the gold values are `%hsap:N%pfal:Y%` and `%btau:N%...%`. Both score as
  `defaulted`, which is exactly the failure this item describes, now with a
  count.
- **4 rows are `included_species` and `excluded_species`**, which are `string`
  with no vocabulary and help reading "for documentation only". The gold values
  are phyletic codes (`pfal`, `hsap`, `MAMM`); the model wrote species names
  (`Plasmodium`, `Homo sapiens`, `P. falciparum`, `all mammals`), which nothing
  refuses. [WDK-SITE-006](../wdk/rules/site-model-params.md) is why that matters:
  those two are the only state the reference client reads back, and they must be
  written together with the pattern and at a different granularity from it.

So the whole criterion this search expresses - which species must have an
ortholog and which must not - is carried by one parameter the model may not
touch and two the model may write anything into. The visible surface and the
answered question have no overlap. A census guard now turns a non-census pattern
into a 422 rather than a plausible count, so the loud half is covered; the
authoring half is not, and no sheet wording fixes it.

# Anchor

`domain/parameters/specs.py:fill_hidden_required_defaults`, its two call sites in
`services/catalog/param_validation.py`, and `services/catalog/param_dag.py:_is_free_text_query`.
Existing coverage is `tests/unit/domain/parameters/test_hidden_required_defaults.py`, which
asserts the fill happens - it does not, and cannot as written, assert anything about
whether the filled value is usable.

Done when the enumeration above exists, the searches whose hidden defaults return nothing
are named, a filled hidden parameter is either verified or surfaced rather than
silently adopted, and `GenesByOrthologPattern` has a contract that produces its
pattern and its two documentation lists from one statement of the criterion,
rather than leaving the pattern unreachable and the lists unconstrained.
