---
type: Decision
title: A small model reads the request; embeddings only shortlist
description: The 0.45 cosine matcher that decided 108 of 237 uncovered gold params is replaced by a luna resolver. Embeddings keep the recall job, where a miss costs a question; the decision job moves to something that understands the sentence.
tags: [agents, parameters, architecture]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# What was decided

`_semantic_value` is deleted. Two injected resolvers replace it, both on
`gpt-5.6-luna`:

- **vocabulary params** -- `narrow_candidates` shortlists with embeddings, then
  the resolver picks one candidate or returns null.
- **vocabulary-less params** (numbers, free text) -- the resolver reads the value
  the request states, or returns null.

Both are injected as a `ValueResolvers` bundle so `services/` never imports
`ai/`. Null means a question, never a WDK default.

# Why embeddings kept the recall job and lost the decision job

They are good at "these 200 of 12,113 are plausible" and bad at "this one".
The asymmetry is what matters: a recall miss produces a question, which is
visible and recoverable; a decision miss produces a bound parameter that looks
answered. `PF00069` scoring against `IPR000023 : Phosphofructokinase_dom` was a
decision miss -- almost nothing instead of 87, verification green.

# Sizing, measured live

| vocabulary | PlasmoDB | Portal |
|---|---|---|
| `GenesByInterproDomain.domain_typeahead` | thousands / 43K tok | **12,113 / 219K tok** |
| `GenesByEcNumber.ec_number_pattern` | 1,079 / 14K | 3,301 / 45K |
| `GenesByOrthologs.organism` | 62 / 0.9K | 675 / 10.5K |

The portal figure is why shortlisting is the mechanism rather than an
optimization: 219K cannot be sent, and paging it across three 100K calls for one
parameter costs more than the problem. Shortlisted, a real call is about 4K.
`MAX_PROMPT_TOKENS = 100_000` is a backstop that should never bind.

# Two guarantees, and one that had to be loosened correctly

The resolver may only return a value it was shown. It answered
`"DeRisi 3D7 Smoothed  (iRBC 3D7 (48 Hour scaled))"` -- the rendered line,
including the display -- and a byte comparison against the value alone threw the
**right answer** away, falling back to the HB3 default, a different experiment.
`match_candidate` now resolves an answer to a candidate by value, rendered line,
or display. Recognising forms we ourselves printed is not leniency; accepting an
answer that matches no candidate still is, and is still refused.

# Cost

The `Agent` constructor calls `infer_model`, which opens a provider client
immediately, so both agents are built on first use rather than at import. A
module-level agent broke every test in the suite by opening an OpenAI client
during collection.

# Evidence

Observed on a multi-criterion request. Before: a list of eight
parameter values to re-type, all stated in the request, and the DeRisi criterion
bound to the wrong profileset. After: the profileset binds correctly, FRAME
reports 0 open questions, and the only questions asked are two genuine
scientific ones -- whether "combine all" over four criteria means union or
intersection, and whether the two evidence arms are OR or AND. Both change the
result; neither is answerable from the request.

# Since extended to multi-pick

A tree-box param keeps its values in `vocab_leaves`, so it reached neither
branch; and a single-value answer would have bound one hour where "20-32 hours"
names thirteen. Both landed together, because fixing only the first turns a
visible question into a silently narrower search. `VocabDecision` now carries a
list, the resolver is told whether the param takes one value or many, and any
element that is not a candidate refuses the whole answer.

**Shortlisting is safe for a single pick and unsafe for a set.** Measured: on
PlasmoDB, `chebi_compound_id` has five figures entries, `go_typeahead` thousands and
`domain_typeahead` thousands -- all multi-pick. Shown the top 200 of five figures, every
value the model returns validates, so an answer missing most of what the
criterion covers is indistinguishable from a complete one. A multi-pick
vocabulary larger than the shortlist is therefore not resolved at all: it becomes
a question. A single pick is unaffected, because its one right answer either
survives the shortlist or the miss becomes a question.

With that in place a multi-criterion request builds end to end: the built strategy, 16
steps, the intended genes, against a reference strategy of 16 steps and the intended genes. What remains
is [an empty DeRisi branch](../backlog/derisi-branch-binds-empty.md).
