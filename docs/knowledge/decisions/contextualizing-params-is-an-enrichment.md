---
type: Decision
title: A contextualized param view is an enrichment, and it has one owner
description: Six call sites asked WDK for a search's params under a context, with four exception types caught and five recoveries between them. The two with no policy at all are exactly where three separate bugs landed.
tags: [wdk-alignment, parameters, resilience, architecture]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# What was decided

`get_search_params_under_context` owns the operation. It narrows a search's
parameters by a context when WDK can narrow them, falls back to the static view
when WDK cannot, and raises only when the static view is unreachable too.

# Why: the seam had no owner

The same class of bug kept coming back, and an audit
proved it. One operation, six implementations:

| site | catches | recovery |
|---|---|---|
| `param_dag._wdk_fetch_at` | -- | **none** |
| `catalog_discovery.get_parameter_options` | -- | **none** |
| `param_validation._refresh_dependent_vocabularies` | `AppError` | static vocab |
| `wdk_conversion` | `AppError` | plain endpoint, else `None` |
| `plan_normalize` | `WDKError` | plain endpoint |
| `param_resolution` | `WDKError` | portal client |

The two with no policy are exactly where the day's bugs landed: parents not
filled before a refresh, a vocabulary read under WDK's defaults instead of the
bound parents, and a 5xx abandoning a criterion. Three symptoms, one missing
abstraction. Fixing them one at a time at their own call sites is why they
looked like an endless supply of new bugs.

# The principle that settles the policy

Contextualizing is an **enrichment**: it replaces a dependent param's static
vocabulary with the one valid under its parents. It is not a precondition for
the parent values being valid, and WDK does not treat it as one. Measured on
live PlasmoDB, `GenesByOrthologPattern`:

| call | result |
|---|---|
| refresh, `organism: ["Plasmodium falciparum 3D7"]` + `profile_pattern` | **500** |
| run, same values, gold parameter set | 200, `totalCount` a large result |

WDK returns 500 on the endpoint that narrows a vocabulary, for a value it
accepts and executes on the endpoint that runs the search. So losing the
narrowing costs vocabulary precision. It must never cost the search.

# What was deliberately left alone

- `param_validation` falls back through the **cached discovery service**, and
  integrations cannot depend on services. Same policy, different layer; it was
  already correct.
- `param_resolution`'s portal fallback answers a different question (this site
  versus the portal), not "can WDK contextualize this".

Claiming those two were unified would be the same overclaiming this decision
exists to correct.

# Evidence it works

Against the live 500, through the real client: one warning line
(`WDK could not contextualize search params; using the static view`) and all six
parameters returned, where the criterion previously died.
