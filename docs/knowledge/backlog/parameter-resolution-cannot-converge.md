---
type: Backlog Item
title: Parameter value resolution is hand-written NLU with no measurement, so it cannot converge
description: Four named rules cover 30 percent of real gold parameters. The other 70 percent fall to cosine similarity or a silent WDK default. Every production failure adds rule N+1, and nothing measures whether the set is getting better.
tags: [agents, parameters, architecture, measurement]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# The pattern that prompted this

Eleven separate parameter defects in one day of live testing, each fixed at its
own call site, each revealing the next: fill ordering, context inheritance, wire
encoding, a 5xx discard, accession-vs-semantic, polarity, vocabulary-less
identifiers, a regex boundary, numeric intent, defaults instructions, quoted
terms. Fixing them individually is not converging, because they are not eleven
bugs. They are one design running out of rules.

# Measured, against ground truth

`thesis/eval/gold_strategies/` holds **20 verified strategies: 334
(search, param, value) triples over 30 searches and 177 distinct params.** Real
WDK values, human-verified. Scoring our named rules against them:

| resolution path | gold params | share |
|---|---|---|
| **no named rule** | **237** | **70%** |
| organism rule | 49 | 15% |
| contrast (ref/comp) rule | 30 | 9% |
| direction rule | 9 | 3% |
| polarity rule (added today) | 9 | 3% |

What the uncovered 237 fall through to, in order: `accession_in_text`, then
`_semantic_value` -- cosine similarity >= 0.45 between the whole criterion text
and each option's display string -- then `_scalar_default` (WDK's own default),
then a Tier-3 question.

Breaking those 237 down by the value the reference strategy actually used:

| shape | count | why it matters |
|---|---|---|
| bare numeric | 69 (29%) | a vocabulary-less number cannot be cosine-matched at all, so it **always** takes WDK's default |
| list / multi-pick | 45 (18%) | sample selectors |
| identifier-shaped | 15 (6%) | covered by the rule added today |
| free text / enum | 108 (46%) | decided by a 0.45 cosine threshold |

The numeric row is the most alarming, because it is silent. "Top 10 percent"
resolving to `min_expression_percentile = 80` (the top **20** percent) is not an
isolated bug -- it is the expected behaviour for 29% of the uncovered params
whenever the request states a quantity.

# Root causes

**R1. It is NLU written in Python, and the tail is unbounded.** Four rules cover
30%. The gold set alone has 177 distinct params across 30 searches; PlasmoDB
publishes 325 searches and the portal 2,356. No hand-written rule set closes
that gap, so every live run finds rule N+1.

**R2. There is no measurement, so every gap looks like a new bug.** Each fix
today was validated by one live run. These 334 triples have been sitting unused.
Without a denominator there is no way to tell a fix from a regression, or to know
how much is left -- which is exactly why the work feels like circling.

**R3. The responsibilities are inverted.** The model holds the intent
("non-syntenic", "top 10 percent", "EC 2.7.-.-"); our code holds the vocabulary
truth. Today our heuristics propose and the model is consulted only after they
fail, via an open slot. The reverse composes correctly: the model proposes a
value for every required param, and the vocabulary validates it with
did-you-mean. **We already have the validating half and it demonstrably works**
-- it is how the model self-corrected `INTERPRO` to `PFAM` once the accession
guard fired.

# Proposed fixes, in order

**F1 - Build the resolver benchmark first.** Each gold step carries a
`displayName` that reads like criterion text ("SNPs: purifying selection
(dn/ds < 1.3)", "In Plasmodium, not human"). Feed (displayName, searchName)
through the real resolver and score against the gold parameters: exact match,
wrong value, asked-when-the-answer-was-known. This converts the whole area from
anecdote to a number, and must land before any redesign so the redesign can be
judged.

**F2 - Invert resolution: the model proposes, the vocabulary disposes.** Require
values for every required param at `set_criterion` (the channel already exists),
keep validation plus did-you-mean as the guard, and delete the heuristics that
are purely NLU -- including `_semantic_value`. Judge it against F1's score
before committing.

**F3 - Keep the rules that encode WDK structure, not language.** The contrast
ref/comp roles, the degenerate-pair guard and organism-scope inheritance are
domain invariants the model cannot infer from a vocabulary listing. They are 27%
of gold params and they should stay.

**F4 - Numbers never take a silent default.** A quantity stated in the request
must bind or open a slot. This is [B17](numeric-intent-ignored-then-reported-as-honoured.md)
generalized from one observation to the 29% it actually affects.

# Anchor

`services/catalog/param_intent.py` (354 lines) and `param_dag.py` (811) hold the
resolution logic; `param_validation.py` (475) and `param_resolution.py` (304)
hold the validating half. Corpus: `thesis/eval/gold_strategies/` (read-only).
Done when the benchmark exists, reports a score, and a redesign is chosen on
that score rather than on the next live run.
