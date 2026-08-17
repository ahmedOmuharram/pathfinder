# Backlog

Everything known to be outstanding, ranked by what actually moves the product. Each item stands alone: a fresh session should be able to pick one up without this conversation.

Items are removed when done, not marked done. The [log](../log.md) records what left.

## Chat

- [FRAME's tool budget does not scale with the problem](frame-budget-does-not-scale.md) - nine criteria do not fit in 60 calls, and the bound ones are discarded

## Agents

- [A numeric bound stated in the request is ignored, then reported as honoured](numeric-intent-ignored-then-reported-as-honoured.md) - the resolution half is closed; a reply can still restate a bound value with an interpretation the value does not support

- [No way for a user to authorise defaults](frame-ignores-use-defaults.md) - the slots now fill, but "pick something sensible" still has no mechanism and an assumed value is only narrated, not recorded

## WDK integration

Ranked by consequence, and each item states its own blast radius rather than leaving it to
be assumed.

- [Filling a hidden required parameter from `initialDisplayValue` chooses the science](hidden-required-default-chooses-the-science.md) - the fill is the right shape and the value it fills carries no guarantee; on one search it is an expression from another site's grammar, and that search is now the largest single source of wrong parameter values

- [34 of the 83 WDK rules have no test; one SILENT rule is open again](wdk-rules-are-unenforced.md) - last in this section because it is mostly the missing safety net under the others, though the one open SILENT rule is a live hazard

## Testing

- [A unit test whose stub misses its seam reaches the live WDK and still passes](unit-tests-can-reach-the-network.md) - nothing in the unit tier refuses sockets; one inert stub was found and fixed, the class is open

## Known and accepted

Not backlog. Recorded as decisions because they were chosen, not deferred:

- [build_strategy is not revision-guarded](../decisions/build-strategy-is-not-revision-guarded.md)
- [No faker or msw generation](../decisions/no-faker-or-msw-generation.md)
- [The nested tree stays at the wire boundary](../decisions/nested-tree-at-the-wire-boundary.md)
