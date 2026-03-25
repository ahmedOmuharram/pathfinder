#!/usr/bin/env python3
"""Scrub leaked secrets from existing VCR cassette YAML files.

Applies the same scrubbing patterns as conftest.py's before_record hooks
to cassettes that were recorded before scrubbing was fully implemented.

WARNING: This script does text-level replacement on YAML files. Cassettes
with HTML in response bodies (e.g., WDK /app page) may become malformed.
Prefer re-recording with --record-mode=all (conftest scrubs at record time)
over post-hoc scrubbing.  Use audit_cassettes.py to verify cleanliness.

Usage:
    uv run python scripts/scrub_cassettes.py --dry-run
    uv run python scripts/scrub_cassettes.py
"""

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Scrubbing patterns (mirrored from conftest.py)
# ---------------------------------------------------------------------------

_USER_ID_RE = re.compile(r"/users/\d+")
_SCRUBBED_USER_PATH = "/users/0"

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

# PII fields in JSON response bodies
_PII_PATTERNS: list[tuple[str, str]] = [
    (r'"email"\s*:\s*"[^"]*"', '"email":"test@test.local"'),
    (r'"firstName"\s*:\s*"[^"]*"', '"firstName":"Test"'),
    (r'"lastName"\s*:\s*"[^"]*"', '"lastName":"User"'),
    (r'"middleName"\s*:\s*"[^"]*"', '"middleName":""'),
    (r'"username"\s*:\s*"[^"]*"', '"username":"test-user"'),
    (r'"organization"\s*:\s*"[^"]*"', '"organization":"Test Org"'),
    (r'"groupName"\s*:\s*"[^"]*"', '"groupName":"Test Group"'),
    (r'"groupType"\s*:\s*"[^"]*"', '"groupType":"research"'),
    (r'"position"\s*:\s*"[^"]*"', '"position":"researcher"'),
    (r'"interests"\s*:\s*"[^"]*"', '"interests":""'),
    (r'"id"\s*:\s*\d{5,}', '"id":0'),
]

# Auth cookies in Set-Cookie headers
_COOKIE_RE = re.compile(r"(Authorization|JSESSIONID|wdk_check_auth)=[^;]+")

# Email addresses outside of JSON fields (catch-all for non-PII contexts)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SAFE_EMAILS = frozenset({"test@test.local", "scrubbed@test.local"})


def _scrub_email(match: re.Match[str]) -> str:
    """Replace real email addresses, preserve test placeholders."""
    email = match.group(0)
    if email in _SAFE_EMAILS:
        return email
    return "scrubbed@test.local"


def scrub_text(text: str) -> str:
    """Apply all scrubbing patterns to cassette YAML text."""
    # Normalize user IDs
    text = _USER_ID_RE.sub(_SCRUBBED_USER_PATH, text)

    # Scrub PII JSON fields
    for pattern, replacement in _PII_PATTERNS:
        text = re.sub(pattern, replacement, text)

    # Scrub auth cookies
    text = _COOKIE_RE.sub(r"\1=SCRUBBED", text)

    # Scrub JWTs
    text = _JWT_RE.sub("JWT_SCRUBBED", text)

    # Scrub remaining email addresses (non-JSON contexts)
    return _EMAIL_RE.sub(_scrub_email, text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrub secrets from VCR cassettes")
    parser.add_argument(
        "--cassette-dir",
        default="src/veupath_chatbot/tests/cassettes",
        help="Path to cassettes directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing",
    )
    args = parser.parse_args()

    cassette_dir = Path(args.cassette_dir)
    if not cassette_dir.is_dir():
        print(f"Error: {cassette_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    files_changed = 0
    files_total = 0

    for path in sorted(cassette_dir.glob("*.yaml")):
        files_total += 1
        original = path.read_text(encoding="utf-8")
        scrubbed = scrub_text(original)

        if scrubbed != original:
            files_changed += 1
            label = "[DRY RUN] " if args.dry_run else ""
            print(f"  {label}{path.name}: scrubbed")
            if not args.dry_run:
                path.write_text(scrubbed, encoding="utf-8")

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{prefix}Files scrubbed: {files_changed}/{files_total}")

    if files_changed == 0:
        print("All cassettes are clean.")


if __name__ == "__main__":
    main()
