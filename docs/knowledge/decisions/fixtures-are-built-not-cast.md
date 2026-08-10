---
type: Decision
title: Fixtures are built, not cast
description: Removing `as Step` from test fixtures restored excess-property checking and exposed fixtures that did not match the API.
tags: [testing, types, frontend]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
status: stable
---

# Why a cast was the problem, not the missing fields

`{ ... } as Step` does two things, and only the first was wanted. It silences the missing required fields, and it **turns off excess-property checking**. So a fixture could set a field the type does not have and nothing failed. Five of them kept setting `isBuilt` long after it was deleted from the backend, the generated types, and every consumer.

`const x: Step = { ... }` silences nothing and checks both directions.

# What removing them found

Thirty-two casts came out, leaving 10 type errors, each a fixture that was lying:

- **A fixture using the wrong API shape.** `SearchNode.test.tsx` passed `parameters: { organism: "Plasmodium" }`, a raw string, where the API returns a typed `ParamValue` (`{ type: "single-pick-vocabulary", value: ... }`). This is the exact failure `CLAUDE.md` warns about: mock data must match real WDK responses, and a cast let it drift.
- **Incomplete `Strategy` fixtures** missing `siteId`, `recordType`, `isSaved`, `createdAt`, `updatedAt`.
- **`StepSnapshot` missing the required `wdkPushError`**, added during R5.
- **Explicit `undefined` into `T | null` fields**, which `exactOptionalPropertyTypes` forbids. Fixed by spreading the partial so absent keys stay absent instead of being enumerated as `undefined`.

The 32 double casts (`as unknown as Strategy`) are replaced by `makeStep` / `makeStrategy` in `lib/types/fixtures.ts`, which build complete objects so overrides are checked at the call site.

# Casts that are not this problem, and stayed

- `[] as Step[]` - an empty array has no properties to check.
- `strategy as Strategy | null` - widening for a `renderHook` generic, not a fixture.
- One `as unknown as StepEditorState` in `SearchTransformBody.test.tsx`. Building a real one means constructing a live TanStack form instance; the cast is confined to one local helper. Left deliberately, not overlooked.

# Anchor

`lib/types/fixtures.ts`. Verified by adding `isBuilt` back to a fixture and confirming `tsc` fails with "Object literal may only specify known properties" - the drift that motivated this is now a compile error.
