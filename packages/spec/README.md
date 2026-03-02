## API spec -- `packages/spec`

This folder contains the OpenAPI specification for the Pathfinder API.

### Contents

- `openapi.yaml` -- the single-file OpenAPI 3.x spec defining all HTTP endpoints, request/response schemas, and SSE event types

### Key API surface areas

The spec covers these endpoint groups:

- **Chat** (`/api/v1/chat`) -- SSE streaming chat endpoint
- **Strategies** (`/api/v1/strategies/`) -- CRUD, plan management, WDK import, counts
- **Steps** (`/api/v1/steps/`) -- Step-level operations
- **Sites** (`/api/v1/sites/`) -- VEuPathDB site catalog and search metadata
- **Models** (`/api/v1/models/`) -- Available LLM model list
- **Experiments** (`/api/v1/experiments/`) -- Experiment CRUD, execution, evaluation, comparison, analysis
- **Plans** (`/api/v1/plans/`) -- Saved plan management
- **Health** (`/api/v1/health`) -- Health check
- **Auth** (`/api/v1/veupathdb-auth/`) -- VEuPathDB authentication proxy
- **Control Sets** (`/api/v1/control-sets/`) -- Experiment control set management

### Update the OpenAPI spec

From repo root:

```bash
cd apps/api
uv run python -m veupath_chatbot.devtools.openapi generate
```

### Generate TypeScript types from the spec

The repo generates TS types from this spec into `packages/shared-ts/src/openapi.generated.ts`.

```bash
cd packages/shared-ts
npm ci
npm run generate:openapi
```
