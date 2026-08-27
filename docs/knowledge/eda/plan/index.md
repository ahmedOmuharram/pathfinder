# EDA integration plan

The batched, verified implementation plan for bringing EDA into PathFinder.
Read [overview.md](overview.md) first: it holds the goal, the layering, the
co-edited SSOT design, the pinned shared contract every batch obeys, the
verification protocol, and the global constraints. Then the batches, in
execution order:

- [Overview](overview.md) - architecture, contract, protocol, constraints
- [Batch 1: Integration foundation](batch-1-integration-foundation.md) - `integrations/eda` models and clients, `domain/eda` predicates
- [Batch 2: Services and catalog](batch-2-services.md) - study catalog with embeddings, analysis authoring, compute orchestration, EDA-backed search detection
- [Batch 3: Conversational backend](batch-3-conversational-backend.md) - the agent toolset, stream parts, the step bridge, persistence, the durable compute
- [Batch 4: Transport and types](batch-4-transport-and-types.md) - the tab's REST router, OpenAPI regeneration, shared part kinds
- [Batch 5: Charts and state](batch-5-charts-and-state.md) - the ECharts foundation in lib, the eda store, API wrappers
- [Batch 6: The EDA tab](batch-6-eda-tab.md) - the workbench-style feature: study picker, subset cell, compute cell, viz cell, step export
- [Batch 7: Chat co-editing and e2e](batch-7-chat-coediting-and-e2e.md) - conversation part renderers, the co-edit loop, end-to-end journeys, closure
