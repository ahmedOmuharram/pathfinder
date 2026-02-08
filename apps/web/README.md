## Pathfinder Web (`apps/web`)

Next.js UI for PathFinder. It provides:

- **Plan mode**: interactive planning sessions, saved planning artifacts, delegation-plan drafting
- **Execute mode**: streaming tool-calling chat that builds/edits a strategy graph

### How it talks to the API

The web app uses Next rewrites to proxy to the backend (see `next.config.js`), so UI requests like `/api/...` forward to the configured API base.

Required env:

- `NEXT_PUBLIC_API_URL` (see `.env.example`)

### Run locally

```bash
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:3000`.

### Scripts

From `package.json`:

- `npm run dev`: start Next dev server
- `npm run build` / `npm run start`: production build + start
- `npm run lint`: ESLint
- `npm run typecheck`: TypeScript (`tsc --noEmit`)
- `npm test`: Vitest
- `npm run check:boundaries`: repo-specific boundary checks

### Shared types

The UI imports shared TypeScript types via the `@pathfinder/shared` path mapping (see `tsconfig.json`) and Next transpiles that package (see `next.config.js`).
