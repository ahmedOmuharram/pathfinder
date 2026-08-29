---
type: Backlog Item
title: The EDA permissions cache is keyed by site alone, so one account's authorization answers every later account in that process
description: Measured 2026-08-29 in the api container - `services/eda/catalog.py::_permissions` caches `/eda/permissions` in a process-global `_SiteCaches.permissions` that nothing clears in production, and a second account's call returns the first account's object (`cached is first` was True). The two credentials on hand, the service account and the dev user, both see 880 datasets all subsettable on plasmodb, so the difference is 0 today and the defect is structural rather than observed. Fix is to key the cache by the caller's token, or to stop caching an account-scoped read at all.
tags: [eda, security, caching, services]
generated: { by: claude-code/opus-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-29T00:00:00Z }
status: stable
---

**What I did.** In the api container, set `veupathdb_auth_token_ctx` to the
service account token, called `services.eda.catalog._permissions("plasmodb")`,
then logged in as the dev user, set the context variable to that token, and
called `_permissions("plasmodb")` again in the same process. Then called
`clear_study_caches()` and called it a third time.

**What I got.**

```
service datasets=880 subsettable=880
dev user through the cache datasets=880 same_object=True
dev user fresh datasets=880 subsettable=880
difference_in_subsettable=0
```

**Why that is wrong.** `/eda/permissions` is the EDA service's answer for the
calling account: it decides which datasets exist for that user, which can be
subset, and which can export rows. `catalog.py` stores it in
`_caches[site_id].permissions`, and `clear_study_caches` has no production
caller, so the first account to ask on a given site decides what every later
account in that api or worker process is told. `resolve_dataset` raises
`UnknownEdaDatasetError` from the same map, so an account can be told a
dataset does not exist, or be offered one it may not read, on another
account's authority.

**Why it happens.** `_permissions` in
`apps/api/src/pathfinder/services/eda/catalog.py` caches an account-scoped
read in a per-site cache. The neighbouring entries in `_SiteCaches`
(`studies`, `index`) really are account-independent: the same 759 studies come
back for the service account and for the dev user, and for plasmodb, toxodb,
hostdb, vectorbase and orthomcl. `permissions` sits in the same dataclass and
inherited its lifetime.

**Fix.** Key the permissions entry by the credential the call carries, or drop
the entry and read `/eda/permissions` per call. A test needs two accounts with
different dataset authorization to pin the behaviour; the two credentials in
`.env.dev` agree on plasmodb, so the pin has to come from a stubbed EDA client.

**What you would get.** Two accounts in one process each read their own
authorization, and a restricted account stops seeing datasets that another
account's token unlocked.
