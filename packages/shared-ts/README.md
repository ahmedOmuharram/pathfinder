## `@pathfinder/shared` (TypeScript) — `packages/shared-ts`

Shared TypeScript types used by the web app (and any TS tooling around the API).

### What lives here

- TS source: `src/`
- Build output (gitignored): `dist/`
- OpenAPI tooling: `scripts/generate-openapi.mjs`

### Common commands

```bash
cd packages/shared-ts
npm ci
npm run build
```

OpenAPI check/generation (see scripts):

```bash
cd packages/shared-ts
npm run check:openapi
```

