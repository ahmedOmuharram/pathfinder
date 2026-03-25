#!/usr/bin/env python3
"""Scan VCR cassette YAML files for leaked secrets.

Detects JWTs, real email addresses, unscrubbed user IDs, auth cookies,
and real passwords. Exits 1 if any leak is found.

Usage:
    uv run python scripts/audit_cassettes.py
    uv run python scripts/audit_cassettes.py --cassette-dir path/to/cassettes
"""

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

# RFC 5322-ish: word chars, dots, hyphens, plus signs @ domain
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SAFE_EMAILS = {"test@test.local", "scrubbed@test.local"}

# /users/<numeric-id> where id != 0
_USER_ID_RE = re.compile(r"/users/(\d+)")

# Authorization= or JSESSIONID= followed by anything other than SCRUBBED
_AUTH_COOKIE_RE = re.compile(
    r"(Authorization|JSESSIONID)=(?!SCRUBBED)([^\s;,\"']+)"
)

# "password" key with a value that is not "SCRUBBED"
_PASSWORD_RE = re.compile(
    r'"password"\s*:\s*"(?!SCRUBBED)([^"]+)"',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------


class Finding:
    __slots__ = ("file", "line_no", "pattern_type", "snippet")

    def __init__(
        self,
        file: Path,
        line_no: int,
        pattern_type: str,
        snippet: str,
    ) -> None:
        self.file = file
        self.line_no = line_no
        self.pattern_type = pattern_type
        self.snippet = snippet[:80]

    def __str__(self) -> str:
        return (
            f"  {self.file.name}:{self.line_no}  "
            f"[{self.pattern_type}]  {self.snippet}"
        )


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def _scan_line(
    path: Path,
    line_no: int,
    line: str,
) -> list[Finding]:
    """Check a single line for all leak patterns."""
    findings: list[Finding] = []

    # 1. JWTs
    findings.extend(
        Finding(path, line_no, "JWT", m.group())
        for m in _JWT_RE.finditer(line)
    )

    # 2. Real email addresses
    findings.extend(
        Finding(path, line_no, "EMAIL", m.group())
        for m in _EMAIL_RE.finditer(line)
        if m.group().lower() not in _SAFE_EMAILS
    )

    # 3. Unscrubbed user IDs (/users/<id> where id != 0)
    findings.extend(
        Finding(path, line_no, "USER_ID", m.group())
        for m in _USER_ID_RE.finditer(line)
        if m.group(1) != "0" and not m.group(1).startswith("999")
    )

    # 4. Unscrubbed auth cookies
    findings.extend(
        Finding(path, line_no, "AUTH_COOKIE", m.group())
        for m in _AUTH_COOKIE_RE.finditer(line)
    )

    # 5. Real passwords
    findings.extend(
        Finding(path, line_no, "PASSWORD", m.group())
        for m in _PASSWORD_RE.finditer(line)
    )

    return findings


def _scan_file(path: Path) -> list[Finding]:
    """Scan a single YAML cassette file for leaked secrets."""
    findings: list[Finding] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        findings.extend(_scan_line(path, line_no, line))
    return findings


def _scan_directory(cassette_dir: Path) -> list[Finding]:
    """Scan all YAML files in the cassettes directory."""
    all_findings: list[Finding] = []
    yaml_files = sorted(cassette_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"WARNING: No .yaml files found in {cassette_dir}")
        return all_findings
    print(f"Scanning {len(yaml_files)} cassette files in {cassette_dir}...")
    for path in yaml_files:
        all_findings.extend(_scan_file(path))
    return all_findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit VCR cassettes for leaked secrets",
    )
    parser.add_argument(
        "--cassette-dir",
        type=Path,
        default=Path("src/veupath_chatbot/tests/cassettes"),
        help="Path to cassettes directory (default: src/veupath_chatbot/tests/cassettes)",
    )
    args = parser.parse_args()

    cassette_dir: Path = args.cassette_dir
    if not cassette_dir.is_dir():
        print(f"ERROR: {cassette_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    findings = _scan_directory(cassette_dir)

    if findings:
        print(f"\nFOUND {len(findings)} potential leak(s):\n")
        for finding in findings:
            print(finding)

        # Summary by type
        by_type: dict[str, int] = {}
        for finding in findings:
            by_type[finding.pattern_type] = (
                by_type.get(finding.pattern_type, 0) + 1
            )
        print("\nSummary by type:")
        for pattern_type, count in sorted(by_type.items()):
            print(f"  {pattern_type}: {count}")

        print(f"\nTotal: {len(findings)} finding(s) across cassettes")
        sys.exit(1)
    else:
        print("\nNo leaks found. All cassettes clean.")
        sys.exit(0)


if __name__ == "__main__":
    main()
