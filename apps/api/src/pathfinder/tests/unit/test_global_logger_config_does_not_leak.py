"""One test's structlog configuration may not decide where a later test logs.

The configuration is process-wide, so the suite restores it around every test.
"""

from __future__ import annotations

import sys

import pytest
import structlog


def test_a_test_may_route_the_global_logger_to_stderr() -> None:
    """A test that reconfigures structlog is allowed to."""
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))

    assert structlog.is_configured()


def test_the_next_test_reads_the_logger_on_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The next test gets the suite's own configuration back."""
    structlog.get_logger("pathfinder.tests.logger_leak").warning("leak marker")
    captured = capsys.readouterr()

    assert "leak marker" in captured.out
    assert "leak marker" not in captured.err
