---
type: Decision
title: An unmatched accession stops the chain
description: A named identifier absent from the vocabulary is a contradiction, not an ambiguity, so it must not fall through to semantic matching.
tags: [agents, parameters, wdk-alignment, data-integrity]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# The failure

Asked on a real account for "P. falciparum 3D7 genes that are kinases, identified by InterPro domain PF00069", the built step was:

```json
"domain_accession":  "PF00069",
"domain_database":   "INTERPRO",
"domain_typeahead":  ["IPR000023 : Phosphofructokinase_dom"]
```

It searched **phosphofructokinase**. Two genes came back instead of ~81, and verification reported success. A researcher reading "kinases with a signal peptide: 3 genes" had no way to see the wrong domain.

# Why it happened, confirmed against live WDK

`PF00069` is a **Pfam** accession. `domain_typeahead`'s vocabulary is **dependent on `domain_database`**: with `INTERPRO` selected it holds 5,405 `IPR` entries, and `PF00069` is genuinely absent (the InterPro equivalent is `IPR000719`).

So the chain ran:

1. FRAME set `database=INTERPRO` (following the user's word "InterPro") alongside a Pfam accession -- an inconsistent pair.
2. The dependent vocabulary refreshed to IPR-only.
3. `accession_in_text` found no match, and **fell through** to the semantic tier.
4. Embedding similarity matched on the substring "kinase" inside "Phosphofructo**kinase**".

Step 3 is the defect. FRAME's own instruction already says that when a value is not in the vocabulary the search *cannot* realize the criterion -- choose another search or drop it, "never guess a value and never invent one". The resolver did the opposite.

# The rule

`names_absent_accession` returns True when the text names an accession and none of them appear in the vocabulary. `map_intent_to_value` then returns `None`, opening a Tier-3 slot, instead of consulting the fuzzy tier.

The distinction that matters: an accession is an **exact** reference. Absent from the vocabulary it is a contradiction to surface, not an ambiguity to resolve by similarity. Text carrying no accession is unaffected and still uses the rule and semantic tiers.

# What it did in practice

Re-running the same request after the fix, the model reconciled its own inconsistency rather than being handed a guess:

| | before | after |
|---|---|---|
| `domain_database` | `INTERPRO` | `PFAM` |
| `domain_typeahead` | `IPR000023 : Phosphofructokinase_dom` | `PF00069 : Pkinase` |
| genes | 2 | 81 |

Blocking the guess did not just avoid a wrong answer; it pushed the model to fix the database to match the accession.

# Anchor

`names_absent_accession` in `services/catalog/param_intent.py`. Guarded by `TestAnExplicitAccessionBlocksGuessing` in `tests/unit/services/catalog/test_param_intent.py`.
