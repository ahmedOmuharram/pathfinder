# Backlog

Everything known to be outstanding, ranked by what actually moves the product. Each item stands alone: a fresh session should be able to pick one up without this conversation.

Items are removed when done, not marked done. The [log](../log.md) records what left.

## Chat

- [FRAME's tool budget does not scale with the problem](frame-budget-does-not-scale.md) - nine criteria do not fit in 60 calls, and the bound ones are discarded

## Agents

- [A dependent vocabulary read before its parent is bound returns the default set](unqualified-dependent-read-shapes-the-answer.md) - the exploratory read has no parent to inherit, and its selection survives

- [The DeRisi expression branch binds to zero genes](derisi-branch-binds-empty.md) - the strategy builds, but an empty branch where a looser binding gave a large result is not obviously right

- [Parameter value resolution is hand-written NLU with no measurement](parameter-resolution-cannot-converge.md) - 4 rules cover 30% of real params; this is the generator behind most of the rest

- [A numeric bound stated in the request is ignored, then reported as honoured](numeric-intent-ignored-then-reported-as-honoured.md) - "top 10 percent" built the top 20 percent and said otherwise

- [FRAME leaves open slots even when told to use defaults](frame-ignores-use-defaults.md) - 9 questions for one request

## WDK integration

- [Orphaned steps are deleted before the push that orphans them](orphan-delete-runs-before-the-orphaning.md) - every delete is refused and the orphans accumulate on the user's account

Ranked by consequence, and each item states its own blast radius rather than leaving it to
be assumed.

- [Logging out deletes PathFinder's cookies and leaves the VEuPathDB token live](logout-call-cannot-invalidate-the-token.md) - ranked first because the outcome is a credential rather than a number; a reading from pinned source, with the live check that settles it

- [FilterMixin is named for view filters and writes step filters, dropping columnFilters on the way](filter-mixin-names-the-wrong-mechanism.md) - the only one here that silently widens a result

- [Non-idempotent POSTs are retried on 5xx and on timeout](post-retried-on-5xx.md) - a proxy 502 after WDK commits leaves orphaned steps and duplicate strategies

- [EXPIRED and INTERRUPTED are treated as fatal although WDK asks for a re-run](expired-and-interrupted-are-not-retried.md) - loud and accurately reported; the cost is a recoverable enrichment abandoned, not a wrong answer

- [A one-sided range serializes to a value WDK rejects](one-sided-range-is-unpushable.md) - loud, but the message never names the missing endpoint

- [The applied-analyses list is always empty, and the emptiness is swallowed](step-analyses-list-silently-empty.md) - no researcher sees it; it blinds the diagnostic written to explain a failed enrichment

- [37 of the 73 WDK rules have no test; the silent ones are now covered](wdk-rules-are-unenforced.md) - last in this section because it is not a defect but the missing safety net under all of them; what remains fails loudly or drifts slowly, so the blast radius is a confusing refusal rather than a plausible number

## Frontend

- [The app fires a doomed WDK auth refresh on every page](doomed-auth-refresh.md) - a guaranteed 401 on every navigation, drowning real console errors

## Known and accepted

Not backlog. Recorded as decisions because they were chosen, not deferred:

- [build_strategy is not revision-guarded](../decisions/build-strategy-is-not-revision-guarded.md)
- [No faker or msw generation](../decisions/no-faker-or-msw-generation.md)
- [The nested tree stays at the wire boundary](../decisions/nested-tree-at-the-wire-boundary.md)
