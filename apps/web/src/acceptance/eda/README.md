# EDA acceptance suite (frontend)

Behavior-only conformance tests for the EDA integration plan, written from
`docs/knowledge/eda/plan/` and the bundle's live-verified values: the store's
reconcile rule, the volcano selection, the transport action union, the parts.

**No-edit rule.** Implementers may not touch `src/acceptance/**`,
`e2e/acceptance/**`, `vitest.acceptance.config.ts` or the `eda-acceptance`
project in `playwright.config.ts`. A wrong test is escalated to the session
lead, the only party who edits the suite.

**Run it:** `npx vitest run --config vitest.acceptance.config.ts` (the default
run never collects `*.acceptance.ts`) and `EDA_ACCEPTANCE=1 npx playwright test
--project=eda-acceptance`. Each suite loads its target through `loadOrSkip`, so
it skips until that batch lands; fixtures are inline by design.
