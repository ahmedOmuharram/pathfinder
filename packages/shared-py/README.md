## `pathfinder-shared` (Python) -- `packages/shared-py`

Shared Pydantic models used across the backend and tooling. These models define the canonical domain types that both the API and any Python tooling reference.

### What lives here

```
src/shared_py/
  __init__.py       # Package init
  models.py         # All shared Pydantic models
```

### Key models

**Strategy plan AST**:
- `SearchNode`, `CombineNode`, `TransformNode` -- tree nodes for the strategy plan
- `PlanNode` -- discriminated union of all node types
- `StrategyPlan` -- complete plan with root node and metadata
- `ColocationParams` -- parameters for genomic colocation operations

**Combine operators**: `CombineOperator` enum (INTERSECT, MINUS, RMINUS, LONLY, RONLY, COLOCATE, UNION) with display labels.

**Strategy types**: `Strategy`, `StrategySummary`, `Step` -- compiled strategy representations.

**Site/catalog types**: `VEuPathDBSite`, `RecordType`, `Search`, `SearchParameter`.

**Chat types**: `ChatMode`, `Message`, `ToolCall`, `ChatRequest`, `Conversation`.

All models use `Field(alias=...)` for camelCase serialization with `populate_by_name=True` for Python-side snake_case access.

### Development

This package is installed as a local dependency of the API (see `apps/api/pyproject.toml`). Changes here are picked up automatically during development.
