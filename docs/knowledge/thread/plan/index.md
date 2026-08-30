# Thread redesign plan

The batched, verified plan that turns the conversation thread into a
science-based reading surface: prose per turn, a quiet trace for tool
activity, flat figures for the typed science parts, task rows for durable
jobs, an approval card only when the user must act, and a dev mode behind the
two settings flags that are dead today.

Read [overview.md](overview.md) first: it holds the pinned wire contract, the
trace grouping rule, the dev-mode rule, the theme rule, the testids that must
survive, the figure style rules, the acceptance layer and its no-edit rule,
the verification protocol, and the global constraints. Then the batches, in
execution order:

- [Overview](overview.md) - contract, acceptance layer, protocol, constraints
- [Batch 0: the acceptance layer](batch-0-acceptance-layer.md) - the frozen
  suites, written before any implementation: one recorded turn pinned in
  vitest, a protocol conformance case for the summary and the grouping, one
  route-mocked e2e journey, and the theme completeness test
- [Batch 1: protocol, runtime, client, tool summaries](batch-1-protocol-and-summaries.md) -
  `data-tool-summary` at 1.4.0, the two reducers, `buildTrace`, and one
  summary written at every registered tool
- [Batch 2: the thread](batch-2-thread.md) - `Trace`, `TraceRow`,
  `TraceGroup`, `TaskRow`, `ApprovalCard`, `Figure`, the dev toggles, and the
  card borders removed
- [Batch 3: tokens and palette](batch-3-tokens.md) - one token layer with a
  light and a dark value for every color, the chart set included, the
  `data-theme` mechanism, and every hardcoded color migrated
