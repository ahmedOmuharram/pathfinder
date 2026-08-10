---
type: Backlog Item
title: A quoted search term in the request is still asked back
description: The prompt says text search for 'kinase' and the free-text param is still opened as a slot, because only identifier-shaped literals are read from the criterion text.
tags: [agents, parameters]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# Symptom

Live PlasmoDB, the 16-step prompt, after the identifier rule landed
([a-value-in-the-request-is-not-a-question](../decisions/a-value-in-the-request-is-not-a-question.md)):

> Text-search term (text_expression) - recommended value: kinase ... Please
> confirm the preferred form.

The request said: **text search for 'kinase'**. The term is quoted, and the
system still asks for it and then recommends the same word back.

# Why the identifier rule does not cover it

`sole_identifier_in_text` reads database-identifier shapes (`PF00069`,
`GO:0016301`, `2.7.-.-`). A search term is an ordinary word, so nothing matches
and the param stays a Tier-3 slot -- correctly, under the current rule, since a
visible vocabulary-less string must not inherit WDK's example default
(`GenesByText` ships `*reductase`).

# The care this needs

A quoted span is a strong signal, but quotes also appear in ordinary prose, and
this param is exactly the one where a wrong value silently changes the science:
the free-text guard exists because inheriting `*reductase` turned an
odorant-binding-protein search into a reductase search.

So the rule wants to be narrow: a quoted span in a criterion whose own text
names the search-term concept, not any quoted span anywhere. Worth confirming
against more than one phrasing before committing.

# Anchor

`sole_identifier_in_text` / `map_intent_to_value` in
`services/catalog/param_intent.py`, and `_is_free_text_query` in
`services/catalog/param_dag.py`. Done when "text search for 'kinase'" binds
`kinase` without asking, and a criterion with no quoted term still asks.
