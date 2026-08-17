---
type: Backlog Item
title: 32 of the 83 WDK rules have no test; every one of them is HARD or CONTRACT
description: The SILENT class - where WDK answers 200 and the science is wrong - is closed for the third time. The 32 untested rules are HARD, where WDK refuses loudly, and CONTRACT, where the mapping drifts over refactors.
tags: [wdk-alignment, testing, knowledge-bundle, silent-failure]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# The gap

`docs/knowledge/wdk/rules/` holds 83 assertions about WDK, each with pinned upstream
evidence and a PathFinder anchor. `scripts/check-wdk-rules.mjs` proves the evidence still
resolves and the anchor still exists. It cannot prove PathFinder still obeys the rule -
only a test does that.

Every `ENFORCED` and `PARTIAL` entry was audited on 2026-08-10 against one standard:
**would the named test or contract go red if the rule were broken?** Touching the same
code was not accepted. Three entries were downgraded on that basis.
[WDK-VOCAB-002](../wdk/rules/parameters-and-vocabularies.md)'s named test drove
`ParameterCanonicalizer` while its anchor is a second, untested expansion in
`integrations/`. [WDK-STRAT-002](../wdk/rules/strategies-and-steps.md) and
[WDK-STRAT-003](../wdk/rules/strategies-and-steps.md) both ran over hypothesis trees built
by `flatten_tree`, so single-rootedness and reachability held *by construction* - the tests
constrained `root_ids` and `subtree_ids` against `flatten_tree` rather than against
anything WDK requires. The counts below are what survived.

Recounted from the rule files on 2026-08-17:

| | UNENFORCED | PARTIAL | ENFORCED | total |
|---|---|---|---|---|
| **SILENT** | **0** | 0 | 32 | 32 |
| HARD | 17 | 3 | 7 | 27 |
| CONTRACT | 15 | 4 | 5 | 24 |
| total | 32 | 7 | 44 | 83 |

A `SILENT` rule is one where WDK accepts the request, returns 200, and the answer is
scientifically wrong - the class of failure a researcher cannot see and PathFinder cannot
report. **That column has now been emptied three times.** It went to 5 on 2026-08-14,
when the `WDK-SITE` family added eight rules, five of them `SILENT` and none of them
tested: [WDK-SITE-002](../wdk/rules/site-model-params.md), `-003`, `-004` and `-005` on the
phyletic profile pattern, and
[WDK-PARAM-010](../wdk/rules/parameters-and-vocabularies.md) on what `initialDisplayValue`
does and does not promise. All five were converted by the changes that fixed the defects
they described - the phyletic widget's grammar carried `-001`, `-002` and `-004` to
`ENFORCED` and `-005` to `PARTIAL`, and the hidden-fill report carried `-003` - which is
how it should go: the tests that pin a defect's fix are the tests the rule wanted.

**It went to 1 and back to 0 on 2026-08-17.**
[WDK-SITE-007](../wdk/rules/site-model-params.md) says a search can offer the same
criterion twice and the query unions the two halves, so filling both returns a superset
measured at 192 genes against 105 on one live pair. `set_criterion` now reads
`radio-params` off the search definition, binds `N/A` into the free-text half, and answers
a criterion written there with a retry naming the vocabulary entries nearest to it.

The rest is unchanged in character: HARD, where WDK refuses and the failure is loud, and
CONTRACT, where the mapping drifts over refactors.

# Order of conversion, and why

## 1. SILENT - closed three times, and closed now

`WDK-SITE-001` through `-005` and `WDK-PARAM-010` were added by the phyletic
research and reopened this section; all six are `ENFORCED`. The last of them was
`WDK-SITE-005`, which was `PARTIAL` while its only test covered the editor widget
and became `ENFORCED` when the backend grew one clade expansion, in
`domain/parameters/phyletic.py:leaf_states`, that both the authoring path and the
wire guard call. `WDK-SITE-007` was the seventh and closed the same day it opened,
by the guard that binds the free-text half off.

The pattern worth keeping: each of those seven was converted **by the change that
fixed the defect the rule described**, not by a separate testing pass. A test
written to pin a fix is a test that fails when the fix regresses; a test written
to satisfy a status column tends not to be.

## 2. HARD, 17 untested and 3 partial

WDK rejects the request, so the failure is loud and nobody publishes on it. The cost is a
build that fails with a message that does not name the cause, and an agent that reads the
refusal as "this criterion cannot be expressed" and drops it. Worth a test, ranked below
SILENT because the wrong answer never leaves the system.

Two are exceptions worth pulling forward: `WDK-PARAM-003` (a two-element single-pick
value) and `WDK-PARAM-006` (a badly formatted date-range bound) both come back **500**,
not 422, so the response is indistinguishable from a WDK bug and carries no diagnosis at
all.

## 3. CONTRACT, 15 untested and 4 partial

PathFinder invariants that keep the mapping honest. They break slowly, over refactors,
rather than at runtime, and several are structural properties an `import-linter` contract
cannot express at all - `WDK-MAP-005` says so in its own body. Convert last, and expect
some of these to need an AST walk rather than a unit test.

## One test closes three uncovered halves - if it runs all three functions

`WDK-STRAT-002`, `WDK-STRAT-003` and `WDK-MAP-003` all name the *same* gap: nothing asserts
what the projection actually hands to `PUT .../step-tree`. **The projection is three
functions, not two**, and a test that stops after the second closes the first two rules and
leaves `WDK-MAP-003` exactly where it was.

In `services/strategies/sync.py`:

1. `pushable_root_id(root.id, graph.steps)` picks the deepest computable step, which is
   what collapses a possibly multi-root map - `session_factory.py` merges every
   `detached_roots` entry into one `steps` dict - down to one pushable id.
2. `rebuild_tree(pushable_id, graph.steps)` rebuilds the nested form. It returns a
   `StrategyStepNode`, which is **PathFinder's** shape, not WDK's. `WDK-STRAT-002` and
   `WDK-STRAT-003` are satisfiable here.
3. `build_step_tree_from_graph(root_step, sync_state.wdk_step_ids)` at
   `sync.py:132-155`, called from `:383`, is what produces the wire shape: a `WDKStepTree`
   of `step_id` / `primary_input` / `secondary_input`, serialized as
   `{stepId, primaryInput, secondaryInput}`. **This is the function `WDK-MAP-003`'s
   uncovered half is about**, and only a test that reaches it covers that rule.

So the test builds a graph with a detached subtree and a half-wired combine, runs all
three, and asserts on the serialized `WDKStepTree`: exactly one root, no step outside the
pushed subtree, and no key other than the three. Note that step 3 needs a `wdk_step_ids`
entry for every step in the pushed tree - it raises `StrategyCompilationError` otherwise -
so the fixture has to supply them, which is easy to miss and turns into a confusing failure
rather than a red assertion.

Highest leverage per test in the whole list, which is why it is called out here rather than
left inside three separate rule bodies. But it earns all three rules only if it runs to
step 3.

# Where the tests go

**Conformance claims** go in `apps/api/src/pathfinder/tests/unit/`, in the directory
mirroring the anchor's package. An anchor in `integrations/veupathdb/strategy_api/` gets a
test under `tests/unit/integrations/veupathdb/`; one in `domain/parameters/` gets
`tests/unit/domain/parameters/`.

**Behavior claims** go in `apps/api/src/pathfinder/tests/integration/strategies/`, which is
the existing live harness: `pytestmark = [pytest.mark.live_wdk, pytest.mark.asyncio]`, the
`live_wdk` marker registered in `apps/api/pyproject.toml`, and that package's `conftest.py`
skipping when `WDK_TEST_EMAIL` / `WDK_TEST_PASSWORD` are unset.

Two things to get right there. First, **most of the live checks this bundle still owes need
no credential** - the bundle's own live verification never authenticates, and `sources.md`
records every outstanding live check as guest-reachable. A guest-reachable probe gated behind
`WDK_TEST_EMAIL` skips for no reason, so either add a credential-free fixture beside the
existing one or assert against an anonymous client directly. Second, **a live test does not
run in CI**, so naming one in a `status` field says the check exists and can be run, not
that it ran on this commit. That is consistent with what the column means everywhere else -
whether the check would fire, not whether the code conforms today - but it is worth stating
in the rule body the way `WDK-VALID-011` does, rather than leaving a reader to assume CI
covers it.

**Put the rule id in the test name**, lowercased with underscores:

```python
def test_wdk_ans_003_num_records_zero_returns_no_records() -> None: ...
```

`check-wdk-rules.mjs` splits a status line on `::` and searches the named file for the
last segment, word-bounded. So the rule's status line becomes:

```
- status: ENFORCED by apps/api/src/pathfinder/tests/unit/services/wdk/test_reports.py::test_wdk_ans_003_num_records_zero_returns_no_records
```

and the gate resolves it. A renamed test then fails the gate instead of silently
un-enforcing the rule.

Two things the audit found that a test author should not repeat:

- **A round trip is not a conformance test.** `tests/unit/domain/parameters/test_value_round_trip.py`
  passes for every value type under any lossless encoding, including one WDK would reject.
  It is why `WDK-PARAM-005`, `WDK-PARAM-006` and `WDK-PARAM-009` are `UNENFORCED` despite
  having tests that name their models. Assert the **wire form**, as
  `test_multipick_empty.py` does for [WDK-PARAM-004](../wdk/rules/parameters-and-vocabularies.md).
- **A contract with a different scope is not enforcement.** Read the contract in
  `apps/api/pyproject.toml` and check it forbids the proposition the rule states, not
  something adjacent to it. [WDK-MAP-005](../wdk/rules/pathfinder-mapping.md) records the
  one time this was got wrong.

One partial credit already exists and should not be redone: `WDK-HTTP-002` is
`UNENFORCED`, but `tests/unit/capabilities/test_resilience.py` already pins
`classify_error(WDKError(status=422)) == SEMANTIC` against 502/503 as `TRANSIENT`. That
covers the derived "nothing below 500 is worth retrying". What is missing is the
`text/plain` body and the 400-against-422 distinction, which `classify_error` collapses.

# Open questions carried in from the rules themselves

None of these blocks a test. Each is a place where a claim could not be sourced, and each
should be settled before the rule that rests on it is treated as settled.

- **Five rules are source-only**, read off the pinned sha and never confirmed against a
  running site: `WDK-STEP-003`, `WDK-STEP-004`, `WDK-STEP-007`, `WDK-ANS-001` (the
  step-report half only) and `WDK-VALID-009` (that `EXPIRED` and `INTERRUPTED` carry
  `requiresRerun`). The table and the reasoning are in
  [sources.md](../wdk/sources.md). Every one is reachable with a guest session.
  `WDK-STRAT-005` was a sixth and has since been settled - the `WDK-VALID-004` experiment
  pushed a step tree over a deliberately invalidated leaf on both sites and got a 204 - so
  what it needs is a test that *pins* the behaviour, not a probe that establishes it.
- **`ValidationLevel` could not be read.** It lives in `org.gusdb.fgputil`, which is not
  one of the four repositories the bundle pins, so `WDK-VALID-007`'s conclusion - that the
  service schema's five-member enum and the platform enum overlap without either
  containing the other - rests on two live probes rather than on the enum. Recorded as
  "we could not read it", not as "it does not exist".
- **No live `date` or `timestamp` parameter was found** on either sampled site, so 8 of
  the 11 parameter types in `WDK-PARAM-001` are observed and 3 are source-only. That is a
  fact about two deployments, not about VEuPathDB.
- **`WDK-FILTER-005` has a measurement without an explanation.** That `estimatedSize`
  tracks `displayTotalCount` is measured; *why* is an open question with two named leads,
  the transcript record class's `getResultSizePlugin()` and the write ordering.
- **The `JSESSIONID` silent-zero did not reproduce.** Three live probes returned full
  result sets with no cookies at all. It is deliberately not a rule; the write-up and the
  capture anyone who reproduces it should take are in
  [transport-quirks](../wdk/rest/transport-quirks.md). The belief is still asserted as
  fact in `CLAUDE.md`, in two docstrings in `integrations/veupathdb/_http.py`, in
  `devtools/diagnosis.py` and in `devtools/README.md`.
- **The `/users/current` 405 could not be confirmed anywhere** - not in WDK, not in
  `wdk-client`, not live. `WDK-HTTP-001` is still right, for the identity reason rather
  than for the 405 in the docstring.

# Done when

Every `SILENT` rule is `ENFORCED` or `PARTIAL` with its uncovered half named, and no rule
carries a status naming a test that would pass with the rule broken. The `HARD` and
`CONTRACT` groups can be split into their own items once `SILENT` is clear; splitting them
now would only produce a backlog that reads like a spreadsheet.
