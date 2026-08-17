---
type: Backlog Item
title: The substitution detector compares filter and input-step params as text, so it can misreport both
description: substituted_params compares a filter value as a raw wire string, and the canonicalizer drops input-step values before the comparison sees them. A filter WDK re-serialized can be reported to the user as a value WDK chose, and an input-step param reads as one the caller never set.
tags: [wdk-alignment, parameters, filters, step-tree, reporting]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# The gap

`substituted_params` answers one question for the user: which of the values in this step are
WDK's rather than the ones the request stated. That answer reaches the model as
`ValidatedParams.substituted`, and `frame_spec.set_criterion` folds it into the criterion's
`defaulted_params`, which is what a reply narrates back
([WDK-PARAM-008](../wdk/rules/parameters-and-vocabularies.md)). A wrong entry there is a
sentence telling a researcher that a value they gave was overridden, or hiding one that was.

The comparison has three cases and only two kinds get one. A vocabulary is compared as a
set of terms, so an expanded branch and a reordered selection are equal. **Everything else
falls through to `ours != echoed_value`, a string comparison on the wire form.**

**A filter parameter is one of the values compared as text.** `FilterValue.to_wire`
serializes `{"filters": [...]}` with `json.dumps` over `FilterTermClause`, which emits
exactly `field`, `type`, `isRange`, `includeUnknown`, `value`, in that order, and parsing
drops every other key the wire carried (`fieldDisplayName` among them). The echo WDK returns
is its own serialization of the same clause set. Two JSON objects that state the same filter
and differ in key order, in whitespace, in a dropped display key, or in the order of the
clauses compare unequal, and the parameter is reported as substituted. The value the user is
told WDK chose is the value they sent.

**An input-step parameter is not compared at all.**
`ParameterCanonicalizer.canonicalize` returns early on `spec.param_type == "input-step"`, so
that name never enters `caller_canonical`, which is what `substituted_params` receives as
`sent`. The detector reads it as a parameter the caller left unset, and any non-empty echo
for it is appended to the substituted list. The wiring of a transform step to its input is
the one value in the step that is structural rather than chosen, and it is the one most
likely to be narrated as a choice WDK made.

Neither case is measured live. Both are readings of the two files below, and the fix and the
tests are the same work either way.

# What it should be

The comparison is per kind, like the vocabulary case already is. A filter is equal when its
clause sets are equal - each clause by field and by its value set, not by its serialization.
An input-step is either compared by the step id the caller wired, or excluded from the
report by name rather than by an accident of canonicalization, and that choice is written
down.

# Anchor

`apps/api/src/pathfinder/services/catalog/wdk_substitution.py:substituted_params` holds the
comparison and `_is_vocabulary`, which is the whole of its kind awareness.
`apps/api/src/pathfinder/services/catalog/param_validation.py:validate_parameters` builds
`caller_canonical` and `echoed` and calls it.
`apps/api/src/pathfinder/domain/parameters/canonicalize.py:ParameterCanonicalizer.canonicalize`
is where the input-step value is dropped.
`apps/api/src/pathfinder/domain/parameters/values.py:FilterValue.to_wire` is the
serialization the text comparison is run against.

Coverage today is `tests/unit/services/catalog/test_wdk_substitution.py`, which has a class
for the vocabulary case and none for either kind here.

Done when a filter is compared as a set of clauses and an input-step has a stated treatment,
both covered by tests in that file that go red if the comparison reverts to raw text.
