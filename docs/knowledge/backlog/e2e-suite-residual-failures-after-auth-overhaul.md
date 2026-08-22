---
type: Backlog Item
title: 10 e2e specs still fail, all deep in composite flows: two real accessibility findings, a shared rail assertion, and tail-of-run flakes
description: Run 23 (2026-08-21) reached 120 passed / 10 failed / 3 skipped / 0 flaky / 0 did-not-run (1.2 h) - the whole feature project is green, including every strategy-edit spec, both purge specs and the enrichment panels. The 10 remaining are deep in composite flows: (a) chat-to-workbench and gene-set-analysis-pipeline fail their axe checkpoint with serious/critical accessibility violations - real product findings these flows never reached before; (b) five site journeys time out waiting for getByTestId('rail-strategy-panel'); (c) three tail-of-run flakes - a composer that never re-enables in 30 s (cross-species), the startup gate exceeding 60 s (plasmodium), and dev-login 500 on worker-40 (toxoplasma) after many worker restarts. Fresh artifacts in apps/web/test-results.
tags: [investigation, e2e, playwright, auth, tests]
generated: { by: claude-code/fable-5, at: 2026-08-20T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-20T00:00:00Z }
status: stable
---

# Investigation (full-suite runs, 2026-08-20/21)

**What I did.** Ran the 133-spec suite repeatedly against the isolated stack while
fixing what each run exposed. After run 12 (105 passed) the fixes were: the mock
follows the FRAME contract (list_searches before binding; the GO criterion carries
go_typeahead only), the readiness ratchet no longer latches a transient DB ping,
the enrichment ceiling is 360 s (measured 163 s solo for five types), the purge
specs assert identity instead of an empty shared account, and the GO spec reads
the vocabulary half and asks its follow-up without a mock marker phrase (a marker
routes the mock into a rebuild that re-mints every step id - measured as the AST
leaf changing from step_65fae9c7 to step_8b4f3fc6 across the question turn).

**What I got.** Run 23: `120 passed / 10 failed / 3 skipped (1.2h)`, zero flaky,
zero did-not-run. Every feature spec is green.

**Why that is wrong.** Ten composite flows still cannot gate a release, and two of
them are failing for reasons users would feel directly (accessibility).

**Why it happens.** (a) `chat-to-workbench` and `gene-set-analysis-pipeline` now
get far enough to run their axe checkpoint and it reports serious/critical
violations - unread until now because the flows died earlier. (b) Five journeys
(crypto, full-researcher-lifecycle, fungal, leishmania, malaria, toxoplasma minus
the flake) wait for `getByTestId('rail-strategy-panel')` and it never shows - one
shared assertion, likely one cause in the right-rail panel wiring. (c) Three are
tail-of-run environment: the composer stayed disabled past 30 s on the second site
of cross-species, plasmodium's page load exceeded the 60 s startup-gate allowance,
and toxoplasma's worker-40 (after many Playwright worker restarts) got a 500 from
dev-login.

**Fix (next session).** Read the axe violation lists from the two cross-feature
traces and fix the components (product work); open one journey trace at the
rail-strategy-panel wait and find why the panel does not render there; rerun the
three flaky ones first on a quiet stack before treating them as real.

**What you would get.** A releasable e2e gate: 133 specs green or knowingly
skipped, on an isolated database, with the auth model the product now enforces.
