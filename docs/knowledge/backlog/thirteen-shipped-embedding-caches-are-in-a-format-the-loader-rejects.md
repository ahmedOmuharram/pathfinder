---
type: Backlog Item
title: Thirteen of the fourteen shipped embedding caches are in a format the loader rejects, so a fresh deployment encodes 7184 entries
description: The per-site .npz files under apps/api/src/pathfinder/data/embeddings ship two shapes. plasmodb carries the content-addressed one the loader reads (keys + embeddings); the other thirteen carry the retired one (embeddings + a scalar hash), which `_load_cached_rows` skips, so they contribute zero rows. Measured 2026-08-27 - 7184 of 7699 shipped catalog entries have no usable row, and the veupathdb portal alone accounts for 2472. A fresh deployment encodes all of them before `/health/ready` reports green, one document at a time. Regenerating the thirteen files in the current format removes the whole first-start encode.
tags: [embeddings, startup, infra, data]
generated: { by: claude-code/opus-5, at: 2026-08-27T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-27T00:00:00Z }
status: stable
---

# What I did

Loaded every shipped catalog snapshot, built its index entries, and counted how
many of them the shipped embedding cache covers:

```
for site in <the fourteen>:
    snapshot = try_load_catalog_cache(site)
    entries  = <one per search, with its enriched text>
    cached   = _load_cached_rows(site)
    uncovered = [e for e in entries if e.cache_key not in cached]
```

# What I got

```
plasmodb:   entries=515  rows=515  uncovered=0
veupathdb:  entries=2472 rows=0    uncovered=2472
vectorbase: entries=923  rows=0    uncovered=923
fungidb:    entries=927  rows=0    uncovered=927
...
total uncovered: 7184
```

`rows=0` on thirteen sites. Reading the files says why:

```
plasmodb  2730 KB  keys=['embeddings', 'keys']  keys:(515,)  embeddings:(515, 768)
toxodb    2128 KB  keys=['embeddings', 'hash']              embeddings:(423, 768)
veupathdb 16068 KB keys=['embeddings', 'hash']              embeddings:(2934, 768)
```

Thirteen files carry `embeddings` plus a scalar `hash`, the shape the cache used
before it became content-addressed. `_load_cached_rows` skips any file without a
`keys` array, so those 43 MB of shipped vectors are never read.

# Why that's wrong

The files exist so a deployment does not encode a catalog it was shipped. With
thirteen of them unreadable, a fresh process encodes 7184 descriptions before
`/health/ready` reports green, and the veupathdb portal's 2472 are the tail that
holds readiness open for the longest. The rows are then written back in the
current format, so the cost is paid once per volume and never seen again - which
is exactly why it has stayed invisible.

# Why it happens

`apps/api/src/pathfinder/data/embeddings/*.npz` was regenerated for plasmodb
when the cache became content-addressed and not for the other thirteen.

# Fix

Regenerate the thirteen files from the catalogs they ship beside, by building
each site's `SemanticSearchIndex` against an empty cache directory and saving
what it produces. A test that reads every shipped file and refuses one without
a `keys` array keeps the two shapes from coexisting again.

# What you'd get

A fresh deployment that encodes nothing at start, and a readiness gate that
closes in seconds rather than waiting on the portal.
