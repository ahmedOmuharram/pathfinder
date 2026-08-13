---
type: Backlog Item
title: Logging out deletes PathFinder's cookies and leaves the VEuPathDB token live
description: The logout route calls WDK /logout with a client carrying no credential, so WDK treats it as a guest and returns before invalidating anything - the bearer token PathFinder captured at login stays valid.
tags: [wdk-alignment, auth, transport, security, integrations]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# What the code does

`POST /api/v1/veupathdb/auth/logout` in
`apps/api/src/pathfinder/transport/http/routers/veupathdb_auth.py` does two things.
It calls VEuPathDB, then it deletes two cookies:

```python
async with httpx.AsyncClient(
    base_url=auth_site.service_url, follow_redirects=True
) as client:
    try:
        await client.get("/logout")
    except httpx.HTTPError:
        logger.warning("Failed to log out of VEuPathDB")
response = JSONResponse({"success": True})
response.delete_cookie(key="Authorization", path="/")
response.delete_cookie(key="pathfinder-auth", path="/")
```

That client is constructed fresh. It has no cookie jar, no `Authorization` header,
and the caller's token is never attached to it - the token lives in the browser's
`Authorization` cookie on **PathFinder's** domain, set by `_build_success_response`
in the same file, and nothing copies it onto this request.

# The reading, and it is a reading

The endpoint reached is
[`SessionService.processLogout`](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/service/SessionService.java#L277-L311).
It resolves `getRequestingUser()` - the identity carried by *that* request - and
then:

```java
// if user is already a guest, no need to log out
if (oldUser.isGuest())
  return createRedirectResponse(redirectUrl).build();
```

A request with no credential is not refused by WDK; a fresh guest is minted for it
([WDK-AUTH-001](../wdk/rules/auth-and-transport.md)). So the requesting user is a
guest, the early return is taken, and no token belonging to the real user is
touched.

The token in question is not short-lived. `POST /login` - the endpoint
`integrations/veupathdb/auth_login.py:password_login` calls - returns a bearer
token cookie whose
[max age is set to three years](https://github.com/VEuPathDB/WDK/blob/e534d2e6a5119165e1742c7a9e07a371217ddda5/Service/src/main/java/org/gusdb/wdk/service/service/SessionService.java#L241-L252),
under a comment saying the secret key should be changed before then.

**Nothing above was confirmed against a live site.** It is read off pinned source
plus PathFinder's own code. The live check that settles it is below, and it needs a
real registered account, which is why no check in the WDK bundle performs it - every
documented verification there is anonymous on purpose.

# Why this ranks where it does

Every other item in this section is about a wrong number or a recoverable failure.
This one is about a credential.

If the reading holds, "log out" means "PathFinder forgot your token", not
"VEuPathDB invalidated it". A token captured before logout - from a shared machine,
a copied browser profile, a proxy log, or anywhere the cookie was readable - keeps
working against plasmodb.org for as long as WDK honours it. The user has been told
they are logged out and the evidence in front of them agrees: the cookies are gone
and the UI is signed out.

That is a security-relevant outcome rather than a wrong status code, which is why
it is ranked above items whose worst case is a bad gene count. It is not ranked as
an emergency: exploiting it needs the token, and getting the token needs access the
attacker could have used directly.

# The live check that settles it

Needs `WDK_DEV_EMAIL` / `WDK_DEV_PASSWORD` sourced into the shell from `.env.dev` -
do not read that file, reference the variables. Four steps, and step 4 is the whole
question.

1. Log in through PathFinder and keep the cookie jar:

   ```bash
   curl -s -c jar.txt -X POST http://localhost:8000/api/v1/veupathdb/auth/login \
     -H 'Content-Type: application/json' \
     -d "{\"email\":\"$WDK_DEV_EMAIL\",\"password\":\"$WDK_DEV_PASSWORD\",\"siteId\":\"plasmodb\"}"
   ```

   Take the `Authorization` value out of `jar.txt`; that string is the WDK bearer
   token.

2. Prove the token is a real, non-guest session:

   ```bash
   curl -s -H "Cookie: Authorization=$TOKEN" \
     https://plasmodb.org/plasmo/service/users/current
   ```

   Expect `"isGuest": false` and the account's email.

3. Log out through PathFinder:

   ```bash
   curl -s -b jar.txt -X POST 'http://localhost:8000/api/v1/veupathdb/auth/logout?siteId=plasmodb'
   ```

4. Repeat step 2 **with the same token string**.

   - Still `"isGuest": false` -> the token survived the logout. Defect confirmed;
     rewrite this item as confirmed and keep it.
   - `401`, or `"isGuest": true` -> WDK invalidated it anyway, by a mechanism not
     visible in `processLogout`. The reading is wrong. **Delete this item** and
     correct [WDK-MAP-005](../wdk/rules/pathfinder-mapping.md) and
     [layer-ownership](../wdk/pathfinder/layer-ownership.md), which both carry the
     same reading and both label it as one.

Do the whole sequence twice, once against a site the account is registered on and
once against a second site, so a per-site auth quirk cannot be mistaken for the
general case.

# What a fix looks like

Forward the credential. The token is already available to the route: the request
carries it as a cookie and `veupathdb_auth_token_ctx` is how the rest of the
codebase hands it to a WDK client. The route already uses `get_wdk_client` in
`_resolve_veupathdb_email` a few lines above, wrapped in exactly that context var.
Doing the same for logout would both fix the call and delete the ad-hoc client,
which is the other half of the problem
([WDK-MAP-005](../wdk/rules/pathfinder-mapping.md): this is the only place outside
`integrations/veupathdb` that opens a connection to a WDK host, and no layering
contract can see it).

Check the failure path while you are there. `httpx.HTTPError` is currently swallowed
into a `warning` and the response still says `{"success": true}`, so even a fixed
call would report success when WDK refused.

# Anchor

`logout` in `transport/http/routers/veupathdb_auth.py`. Done when the request to
WDK carries the user's token, when a WDK refusal is visible to the caller rather
than logged, and when a test asserts the outbound request carries an
`Authorization` credential.
