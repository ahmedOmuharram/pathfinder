## `@pathfinder/shared` (TypeScript) -- `packages/shared-ts`

Shared TypeScript types and validators used by the web app and any TS tooling around the API.

### What lives here

```
src/
  index.ts                 # Package entry point (re-exports types.ts)
  types.ts                 # Core type definitions and constants
  zod.ts                   # Zod runtime validators for API payloads
  openapi.generated.ts     # Auto-generated types from OpenAPI spec
```

### Key exports

**Combine operators**: `CombineOperator` enum, labels, WDK operator mappings, and conversion helpers (`wdkOperatorToCombine`, `getOperatorDisplayLabel`).

**Strategy plan AST**: `PlanStepNode` (recursive tree node), `ColocationParams`, `BasePlanNode`. The AST represents WDK strategy graphs as a tree of search, combine, and transform nodes.

**Step and strategy types**: `Step`, `Strategy`, `StrategySummary`, `StepFilter`, `StepAnalysis`, `StepReport`.

**Chat types**: `ChatMode`, `Message`, `ToolCall`, `ChatRequest`, `Conversation`.

**Site types**: `VEuPathDBSite`, `RecordType`, `Search`, `SearchParameter`.

**Zod validators** (`zod.ts`): Runtime validation schemas mirroring the TypeScript types. Used for API payload validation.

**OpenAPI generated types** (`openapi.generated.ts`): Auto-generated from `packages/spec/openapi.yaml`. Do not edit manually.

### How the web app imports these

The web app uses TS path mapping (`@pathfinder/shared`) configured in `apps/web/tsconfig.json`. Next.js transpiles this package automatically via `transpilePackages` in `next.config.js`.

### Common commands

```bash
cd packages/shared-ts
npm ci
npm run build
```

Regenerate OpenAPI types from the spec:

```bash
npm run generate:openapi
```

Validate that generated types match the spec:

```bash
npm run check:openapi
```
