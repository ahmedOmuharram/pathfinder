## API spec -- `packages/spec`

This folder contains the OpenAPI specification for the Pathfinder API.

### Contents

- `openapi.yaml` -- the single-file OpenAPI 3.x spec defining all HTTP endpoints, request/response schemas, and SSE event types

### Key API surface areas

The spec covers these endpoint groups:

- **Chat** (`/api/v1/chat`) -- SSE streaming chat endpoint
- **Strategies** (`/api/v1/strategies/`) -- CRUD, plan management, WDK import, counts
- **Steps** (`/api/v1/steps/`) -- Step-level operations
- **Sites** (`/api/v1/sites/`) -- VEuPathDB site catalog and search metadata, including sub-routes for catalog, genes, and parameters
- **Models** (`/api/v1/models/`) -- Available LLM model list
- **Experiments** (`/api/v1/experiments/`) -- Experiment CRUD, execution, evaluation, comparison, analysis
- **Plans** (`/api/v1/plans/`) -- Saved plan management
- **Gene Sets** (`/api/v1/gene-sets/`) -- Gene set CRUD and management
- **Exports** (`/api/v1/exports/`) -- Data export endpoints
- **Operations** (`/api/v1/operations/`) -- Long-running operation tracking
- **User Data** (`/api/v1/user-data/`) -- User data management
- **Tools** (`/api/v1/tools/`) -- Tool listing
- **Health** (`/api/v1/health`) -- Health check
- **Auth** (`/api/v1/veupathdb-auth/`) -- VEuPathDB authentication proxy and dev login (`/api/v1/dev/`)
- **Dev** (`/api/v1/dev/`) -- Dev login and utilities
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
