---
type: Backlog Item
title: yarn generate:types against a mock-mode API writes /api/v1/dev/login into the committed spec
description: The root generate:types script dumps /openapi.json from whichever api container is running; with PATHFINDER_CHAT_PROVIDER=mock (the e2e overlay) the app mounts /api/v1/dev/login, so the dump adds DevLogin types, hooks and zod plus three barrel edits to packages/shared-ts/src/generated and packages/spec/openapi.json. Measured on 2026-08-29 during the EDA batch-7 freshness check: 8 files differed after a mock-mode run and zero after re-running against the non-mock container. A regeneration done while the e2e stack is up silently commits a dev-only route.
tags: [tooling, kubb, openapi, e2e]
generated: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
status: stable
---

**What I did.** Ran `yarn generate:types` twice and checksummed the 1066
generated files plus `openapi.json`: once with the api container on the e2e
overlay, once on the dev env.

**What I got.** Mock mode: `hooks/useDevLogin.ts`, `types/DevLogin.ts`,
`zod/devLoginSchema.ts` added, three `index.ts` barrels and `openapi.json`
changed. Dev mode: no difference.

**Why that is wrong.** A regeneration done at the wrong moment ships a
dev-only route into the shared contract and the client types.

**Why it happens.** The dev-login route is mounted conditionally on the chat
provider, and the generator does not check which mode it is talking to.

**Fix.** Have the generator refuse (non-zero exit with the reason) when the
dumped spec contains `/api/v1/dev/login`, or dump the spec from an
in-process app built with the production settings instead of the running
container.

**What you would get.** A regeneration that cannot depend on which compose
overlay happens to be up.
