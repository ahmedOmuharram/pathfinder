# Backlog

Everything known to be outstanding, ranked by what actually moves the product. Each item stands alone: a fresh session should be able to pick one up without this conversation.

Items are removed when done, not marked done. The [log](../log.md) records what left.

## Chat

- [FRAME's tool budget does not scale with the problem](frame-budget-does-not-scale.md) - nine criteria do not fit in 60 calls, and the bound ones are discarded

## Agents

- [Parameter value resolution is hand-written NLU with no measurement](parameter-resolution-cannot-converge.md) - 4 rules cover 30% of real params; this is the generator behind most of the rest

- [A quoted search term in the request is still asked back](quoted-term-is-still-a-question.md) - the value is in the prompt, in quotes

- [A numeric bound stated in the request is ignored, then reported as honoured](numeric-intent-ignored-then-reported-as-honoured.md) - "top 10 percent" built the top 20 percent and said otherwise

- [FRAME leaves open slots even when told to use defaults](frame-ignores-use-defaults.md) - 9 questions for one request

## WDK integration

Ranked by consequence, and each item states its own blast radius rather than leaving it to
be assumed.

- [FilterMixin is named for view filters and writes step filters, dropping columnFilters on the way](filter-mixin-names-the-wrong-mechanism.md) - the only one here that silently widens a result

- [WDK's "result not ready" sentinel is read as data](delayed-result-sentinel-unhandled.md) - a retryable condition surfaces as a parse error, or vanishes

- [Non-idempotent POSTs are retried on 5xx and on timeout](post-retried-on-5xx.md) - a proxy 502 after WDK commits leaves orphaned steps and duplicate strategies

- [A one-sided range serializes to a value WDK rejects](one-sided-range-is-unpushable.md) - loud, but the message never names the missing endpoint

## Frontend


- [The app fires a doomed WDK auth refresh on every page](doomed-auth-refresh.md) - a guaranteed 401 on every navigation, drowning real console errors

## Known and accepted

Not backlog. Recorded as decisions because they were chosen, not deferred:

- [build_strategy is not revision-guarded](../decisions/build-strategy-is-not-revision-guarded.md)
- [No faker or msw generation](../decisions/no-faker-or-msw-generation.md)
- [The nested tree stays at the wire boundary](../decisions/nested-tree-at-the-wire-boundary.md)
