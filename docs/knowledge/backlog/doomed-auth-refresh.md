---
type: Backlog Item
title: The app fires a doomed WDK auth refresh on every page
description: auth/status returns 200 saying there is no WDK session, then the app POSTs auth/refresh anyway and takes a 401, on every navigation.
tags: [frontend, auth, noise]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
status: stable
---

# Observed

Browser session against the running app, three consecutive page loads (chat, workbench, saved):

```
GET  /api/v1/veupathdb/auth/status?siteId=plasmodb   -> 200
POST /api/v1/veupathdb/auth/refresh?siteId=plasmodb  -> 401
```

Every navigation repeats the pair, and each 401 lands in the browser console as an error. Nothing else on the page misbehaves, so this is noise rather than breakage -- but it is noise that makes a real console error easy to miss, and it is a guaranteed-to-fail request on a hot path.

# Why it matters beyond tidiness

The status call already answers the question the refresh is asking. Firing the refresh regardless means every user without a live WDK session, including guests, pays a round trip and sees console errors on every page.

# Where to look

The refresh is issued after `auth/status` resolves. Gate it on what status returned instead of calling unconditionally.

# Caveat on how it was found

Observed under the e2e mock stack, where the dev-login user has no WDK identity by construction. Confirm against a real signed-out session before assuming the same sequence -- it may be that status reports "not authenticated" and the refresh is a deliberate one-shot attempt to establish a guest token, in which case the fix is to stop treating its 401 as an error rather than to stop calling it.

# Anchor

`apps/web` auth hooks calling `/api/v1/veupathdb/auth/refresh`. Done when a signed-out page load produces no console errors.
