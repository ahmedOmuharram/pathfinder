---
type: Decision
title: One way to generate types
description: The docker codegen service and its script were a second, silently broken path to what yarn generate:types already does, so they were deleted.
tags: [codegen, tooling, ssot]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
status: stable
---

# What was found

`CLAUDE.md` names one command for regenerating types: `yarn generate:types` at the repo root. A second path existed anyway: a `codegen` service in `docker-compose.dev.yml` (behind `profiles: ["dev"]`) running `scripts/sync-api-types.sh`.

That script called `yarn generate:openapi`, **a script that no longer exists**. It had been renamed to `generate`. So the second path was broken, and because it sat behind a profile nobody ran, nothing reported it. Three READMEs documented the same dead command, and one documented `yarn check:openapi`, which is really `check:generated`.

# The decision

Delete the second path rather than repair it. `scripts/sync-api-types.sh` and the `codegen` service are gone; the READMEs point at `yarn generate:types`.

Repairing it would have restored two ways to do one thing, which is how it drifted in the first place. A path that nothing exercises will rot again, and a profile-gated service is exactly the kind of thing no gate covers.

# Why no checker for this

A gate that resolves every ``yarn <script>`` mentioned in a README would need to infer which package each snippet runs in, which is guesswork and would produce false failures. A flaky gate is worse than none. The defence here is having one path, not policing several.

# Anchor

`package.json` at the repo root owns `generate:types`. Done if `docker-compose.dev.yml` ever regrows a codegen service, or a README names a script its package.json does not define.
