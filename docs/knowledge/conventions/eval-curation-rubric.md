---
type: Convention
title: The eval curation rubric: what a staged candidate must satisfy to be promoted
description: The rules a human applies when promoting a staged eval candidate into the corpus. Curation stays human; this rubric makes it fast and consistent. Approved by the owner 2026-08-23.
tags: [evals, curation, privacy]
generated: { by: claude-code/fable-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-23T00:00:00Z }
status: stable
---

Promotion turns a staged candidate (request + built strategy + outcome, user
linkage still present) into a permanent corpus case (linkage stripped by the
promotion constraint). A case is promoted only if every rule below holds; a
candidate that fails any rule is edited until it passes or discarded. The
curator's judgment outranks this rubric; when it does, the case records why.

## Privacy (hard rules, never overridden)

1. No person, lab, institution, grant, cohort, or unpublished-project context
   survives in any field. "My lab's Duffy screen list" fails; "a list of 46
   P. falciparum gene ids" passes. Rewriting the request to remove context is
   allowed and preferred over discarding, provided rule 5 still holds.
2. No free-text that could identify a user by writing style quirks, signatures,
   or self-reference ("as I said in my thesis").
3. Gene ids, organisms, GO terms, search names and counts are science, not
   identity: they stay.
4. If in doubt, discard. The corpus never needs any single case.

## Quality (what makes a case worth keeping)

5. The case has a determinable expectation, stated as one of: a known-good
   strategy shape (criteria + operators, not exact WDK ids), a required
   behavior (must clarify first; must not build; must ask approval), or a
   measurable outcome (result set within a stated tolerance of a reference).
   "Interesting conversation" with no checkable expectation is not a case.
6. The case names the failure it guards against - ideally a backlog item,
   log entry, or observed regression. A case that guards nothing is weight.
7. Near-duplicates collapse: two requests exercising the same behavior with
   different nouns become one case (keep the clearer one). Deliberate
   variants (same intent, different specificity tier) are not duplicates.
8. The expectation must hold under a real model, not only under the mock.
   A case whose pass depends on the mock's marker routing is a pipeline test
   and belongs in the integration suite, not the corpus.

## Mechanics

9. Provenance carries: site, assistant, promotion date, staging id - never
   the user. The promotion constraint enforces the last clause; the curator
   enforces the rest of rule 1 because regex cannot.
10. Every promoted case runs once (mock) before the promotion is committed;
    a case that errors is not promoted.
11. Cadence: review the staged queue weekly; a queue older than two weeks is
    a signal the rubric or the cadence is wrong, not that curation should be
    automated.
