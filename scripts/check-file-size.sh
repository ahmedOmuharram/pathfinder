#!/usr/bin/env bash
# Fail if any Python source file exceeds MAX_LINES (excluding blanks/comments).
# Usage: check-file-size.sh [dir] [max_lines]
set -euo pipefail

DIR="${1:-apps/api/src}"
MAX="${2:-300}"
violations=0

while IFS= read -r f; do
    # Count non-blank, non-comment lines
    count=$(grep -cvE '^\s*($|#)' "$f" 2>/dev/null || echo 0)
    if [ "$count" -gt "$MAX" ]; then
        echo "  $f: $count lines (max $MAX)"
        violations=$((violations + 1))
    fi
done < <(find "$DIR" -name '*.py' -not -path '*/__pycache__/*' -not -path '*/tests/*' -not -path '*/seed/seeds/*' -not -path '*/ai/prompts/*')

if [ "$violations" -gt 0 ]; then
    echo ""
    echo "FAIL: $violations file(s) exceed $MAX lines (excluding blanks/comments)"
    exit 1
else
    echo "check-file-size: all files under $MAX lines"
fi
