## API spec — `packages/spec`

This folder contains the OpenAPI specification for the Pathfinder API:

- `openapi.yaml`

### Update the OpenAPI spec

From repo root:

```bash
cd apps/api
uv run python -m veupath_chatbot.devtools.openapi generate
```

### Generate TypeScript types from the spec

The repo generates TS types from this spec into `packages/shared-ts/src/openapi.generated.ts`.

From repo root:

```bash
cd packages/shared-ts
npm ci
npm run generate:openapi
```

