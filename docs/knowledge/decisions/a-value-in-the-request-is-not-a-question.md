---
type: Decision
title: A value the request already states is not a question
description: Three resolution gaps in one run, all the same shape - the answer was in the criterion text and we asked anyway, or invented one. Polarity, vocabulary-less identifiers, and an EC wildcard the accession regex could not match.
tags: [agents, parameters, correctness]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# The shape

Three separate failures on the 16-step prompt, all reducible to: the criterion
text carried the answer, and resolution either asked for it or made one up.

## 1. Polarity

`GenesByOrthologs.isSyntenic` is a vocabulary of exactly `['yes', 'no']`. The
request said "non-syntenic orthologs". Nothing mapped the phrasing to the
vocabulary, so the model supplied its own wording and WDK answered
`Parameter 'isSyntenic' does not accept 'Non-syntenic'`.

The param name carries the concept (`isSyntenic` -> "syntenic") and the text
carries the polarity, so `_boolean_polarity` reads both. Silence still resolves
to nothing: a criterion that never mentions synteny leaves the param to its own
default rather than picking a side.

## 2. An identifier with no vocabulary to check it against

`GenesByEcNumber.ec_wildcard` is a visible required `string` with no vocabulary
and the placeholder default `'N/A'`. Refusing that default is right. Asking the
user to confirm the `2.7.-.-` they had already written is not.

`accession_in_text` recognized the shape but only matched against vocabulary
options, so a param with no options could never be answered by it.
`sole_identifier_in_text` handles that case: with nothing to validate against,
the literal in the request is the value and WDK is what checks it. Two
identifiers in one criterion stays a question -- guessing which one a param
wants is how `PF00069` once became a phosphofructokinase domain.

## 3. The regex could not match the most common EC form

`_ACCESSION_RE` ended in `\b`. An EC wildcard ends in a hyphen, and `\b` requires
a word character before it, so `2.7.-.-` matched nothing at all -- in this rule
and in every other caller of that regex. The trailing boundary is now a
lookahead.

# Why they are recorded together

Individually each looks like a small parsing miss. Together they are one
principle the resolver was not applying: **a value the user stated is not a
question, and it is not an invitation to guess either.** The two failure modes
are symmetric, and both were present in a single run.

# Evidence

Live PlasmoDB, same prompt, across three runs:

| run | outcome |
|---|---|
| before | FRAME exhausted its 60-call budget; nothing built |
| after polarity + partial-progress | FRAME completed; BUILD stopped on `ec_wildcard` |
| after the identifier rule | FRAME reports **0 open questions**; `ec_wildcard` resolved |

# What is still asked, correctly

`ms_assay` -- the request says "trophozoite samples" without naming a WDK
experiment, so there is a real choice only the user can make. That question is
the system working.
