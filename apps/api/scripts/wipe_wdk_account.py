#!/usr/bin/env python3
"""Wipe all strategies from a WDK dev account.

Used before and after cassette recording to ensure a clean account state.

Usage:
    # Interactive (prompts for confirmation):
    uv run python scripts/wipe_wdk_account.py

    # Non-interactive (CI):
    uv run python scripts/wipe_wdk_account.py --yes

Environment variables:
    WDK_AUTH_EMAIL      Account email (required)
    WDK_AUTH_PASSWORD   Account password (required)
    WDK_TARGET_SITE     Site slug (default: plasmodb)
    WDK_WIPE_CONFIRM    Set to "1" to skip confirmation (alternative to --yes)
"""

import argparse
import asyncio
import os
import sys

import httpx

# Site slug -> WDK service base URL
SITE_URLS: dict[str, str] = {
    "plasmodb": "https://plasmodb.org/plasmo/service",
    "toxodb": "https://toxodb.org/toxo/service",
    "cryptodb": "https://cryptodb.org/cryptodb/service",
    "giardiadb": "https://giardiadb.org/giardiadb/service",
    "amoebadb": "https://amoebadb.org/amoeba/service",
    "microsporidiadb": "https://microsporidiadb.org/micro/service",
    "piroplasmadb": "https://piroplasmadb.org/piro/service",
    "tritrypdb": "https://tritrypdb.org/tritrypdb/service",
    "trichdb": "https://trichdb.org/trichdb/service",
    "fungidb": "https://fungidb.org/fungidb/service",
    "vectorbase": "https://vectorbase.org/vectorbase/service",
    "hostdb": "https://hostdb.org/hostdb/service",
}


def _get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: {name} environment variable is required", file=sys.stderr)
        sys.exit(1)
    return value


def _extract_auth_cookie(headers: httpx.Headers) -> str | None:
    """Extract the Authorization cookie value from response headers."""
    for header in headers.get_list("set-cookie"):
        if header.startswith("Authorization="):
            value = header.split(";", 1)[0].split("=", 1)[1]
            return value.strip('"')
    return None


async def _login(base_url: str, email: str, password: str) -> str:
    """Authenticate to WDK and return the Authorization cookie value."""
    async with httpx.AsyncClient(
        base_url=base_url, follow_redirects=False, timeout=30.0
    ) as client:
        response = await client.post(
            "/login",
            json={
                "email": email,
                "password": password,
                "redirectUrl": base_url.rsplit("/service", 1)[0],
            },
        )

    token = _extract_auth_cookie(response.headers)
    if not token:
        print(
            "ERROR: Login failed — no Authorization cookie in response",
            file=sys.stderr,
        )
        print(f"  Status: {response.status_code}", file=sys.stderr)
        sys.exit(1)

    return token


async def _wipe_strategies(base_url: str, auth_token: str) -> int:
    """Delete all strategies for the authenticated user. Returns count deleted."""
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        cookies={"Authorization": auth_token},
        timeout=30.0,
    ) as client:
        response = await client.get("/users/current/strategies")
        response.raise_for_status()
        strategies = response.json()

        if not strategies:
            print("No strategies to delete.")
            return 0

        print(f"Found {len(strategies)} strategies to delete...")

        deleted = 0
        for strategy in strategies:
            strategy_id = strategy.get("strategyId") or strategy.get("id")
            if strategy_id is None:
                continue
            try:
                resp = await client.delete(
                    f"/users/current/strategies/{strategy_id}"
                )
                resp.raise_for_status()
                deleted += 1
                print(f"  Deleted strategy {strategy_id}")
            except httpx.HTTPStatusError as exc:
                print(
                    f"  WARNING: Failed to delete strategy {strategy_id}: "
                    f"{exc.response.status_code}",
                    file=sys.stderr,
                )

    return deleted


async def _run(base_url: str, email: str, password: str, site: str) -> None:
    """Authenticate and delete all strategies (async I/O only)."""
    print(f"Authenticating as {email} on {site}...")
    auth_token = await _login(base_url, email, password)
    print("Authenticated successfully.")

    deleted = await _wipe_strategies(base_url, auth_token)
    print(f"Done. Deleted {deleted} strategies.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wipe all strategies from a WDK account"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    email = _get_env("WDK_AUTH_EMAIL")
    password = _get_env("WDK_AUTH_PASSWORD")
    site = os.environ.get("WDK_TARGET_SITE", "plasmodb").strip()

    base_url = SITE_URLS.get(site)
    if not base_url:
        print(
            f"ERROR: Unknown site '{site}'. "
            f"Valid: {', '.join(SITE_URLS)}",
            file=sys.stderr,
        )
        sys.exit(1)

    skip_confirm = args.yes or os.environ.get("WDK_WIPE_CONFIRM") == "1"
    if not skip_confirm:
        print(f"About to wipe ALL strategies from: {email} on {site}")
        print(f"  Service URL: {base_url}")
        answer = input("Continue? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    asyncio.run(_run(base_url, email, password, site))


if __name__ == "__main__":
    main()
