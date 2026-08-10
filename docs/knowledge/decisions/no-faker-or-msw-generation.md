---
type: Decision
title: No faker or msw generation
description: Reproduced the incompatibility, found it structural in the plugin, and concluded the output would fight this codebase's testing rules anyway.
tags: [codegen, testing, kubb, wont-do]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
status: stable
---

# What was tried

Both plugins were installed at 4.37.2, matching the Kubb siblings (4.39.3 is inside the repo's 7-day `npmMinimalAgeGate`, a deliberate supply-chain policy that was not weakened for this). Generation itself succeeds: 1441 files, six plugins, no errors.

Typechecking is where it fails, and the first result was a false green. `packages/shared-ts/tsconfig.json` **excludes `src/generated`**, so `tsc` reported zero errors without looking at any generated file. Checked properly, with `src/generated` included: **586 errors**.

# The mechanism, which is not what the old note said

The note blamed enums. It is not enums. Every faker factory is emitted as:

```ts
export function createX(data?: Partial<X>): X {
  return { ...{ /* faker defaults */ }, ...data || {} }
}
```

Spreading a `Partial<T>` gives each optional key the type `K | undefined`. Under `exactOptionalPropertyTypes: true`, a property declared `kind?: K` accepts absence or `K`, but never an explicit `undefined`. So the return value cannot be assigned to `T`. Enum properties merely happen to be reported first.

That override shape is hardcoded in `@kubb/plugin-faker`. None of its options (`mapper`, `override`, `regexGenerator`, `transformers`, `seed`) change it, so there is no configuration that fixes this.

# Why it is not worth patching

Even with the types fixed, the output would fight this project's testing rules. `CLAUDE.md` requires that mock data be validated against real WDK responses with real field names, and that tests assert correctness (gene counts, field names, real data) rather than existence. A generated factory fills `searchName` with `faker.string.alpha()`. Tests built on it pass against nonsense, which is the failure mode those rules exist to prevent. Generated msw handlers inherit the same data.

So the cost is a patch script to maintain, a new dependency, and roughly 500 generated files, in exchange for a facility the testing rules discourage using.

# What the real problem was

The backlog item justified faker by pointing at fixture drift: five test fixtures still set `isBuilt` long after the field was deleted from the backend and the generated types. Random data would not have caught that. **Type-checked** fixtures would have, instantly. The `as Step` cast in those helpers is what hid it, and that is now its own backlog item.

# Anchor

`packages/shared-ts/kubb.config.ts` lists four plugins. Revisit only if Kubb changes the override shape upstream, and only alongside a concrete use that does not violate the real-data rule.
