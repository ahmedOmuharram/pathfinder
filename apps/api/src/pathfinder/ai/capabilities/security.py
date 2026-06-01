from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from pathfinder.ai.capabilities.piguard import (
    InvisibleTextScanner,
    PIGuardScanner,
    SecurityRejectionError,
    resolve_model_dir,
)
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


_PURE_APPROVAL_BYPASS = re.compile(
    r"""^\s*(?:
        yes|yep|yeah|ok|okay|sure|fine|
        approved?|proceed|go(?:\s+ahead)?|continue|
        run\s+it|execute(?:\s+(?:it|the\s+plan))?|launch(?:\s+it)?|
        do\s+it|confirm(?:ed)?|accept(?:ed)?|
        sounds?\s+good|looks?\s+good|
        perfect|great
    )[\s\.\!\,]*$""",
    re.IGNORECASE | re.VERBOSE,
)

_APPROVAL_CONNECTIVE_RE = re.compile(
    r"^\s*(?P<head>[^,.\!\?]{0,40}?)\s*[,\.]\s*(?P<tail>[^,.\!\?]{0,40})[\s\.\!\?]*$",
)

_MAX_APPROVAL_LENGTH = 80


def _is_pure_approval(text: str) -> bool:
    """Strict whitelist: the text is nothing more than an approval phrase.

    Bypassing PIGuard is only safe when the reply is demonstrably a short
    affirmation with no room for injected instruction. This is stricter
    than ``classify_approval_reply``, which accepts change-requests that
    also read affirmative.
    """
    stripped = text.strip()
    if not stripped or len(stripped) > _MAX_APPROVAL_LENGTH:
        return False
    if _PURE_APPROVAL_BYPASS.match(stripped):
        return True
    match = _APPROVAL_CONNECTIVE_RE.match(stripped)
    if match is None:
        return False
    head = match.group("head") or ""
    tail = match.group("tail") or ""
    return bool(
        _PURE_APPROVAL_BYPASS.match(head)
        and _PURE_APPROVAL_BYPASS.match(tail),
    )


@dataclass
class UserInputScanner:
    """Single-scan-per-turn trust boundary for user input.

    The scanners are lazy-initialised under a lock so the first caller
    pays the onnxruntime + tokenizer load once. ``warm_up_piguard`` at
    startup primes the OS page cache so the first real scan is fast.
    """

    injection_threshold: float = 0.90
    model_dir: Path = field(default_factory=resolve_model_dir)
    _piguard: PIGuardScanner | None = field(default=None, init=False, repr=False)
    _invisible: InvisibleTextScanner | None = field(
        default=None, init=False, repr=False,
    )
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False,
    )

    def _ensure_initialised(self) -> tuple[PIGuardScanner, InvisibleTextScanner]:
        if self._piguard is not None and self._invisible is not None:
            return self._piguard, self._invisible
        with self._lock:
            if self._piguard is None:
                self._piguard = PIGuardScanner(
                    model_dir=self.model_dir,
                    threshold=self.injection_threshold,
                )
            if self._invisible is None:
                self._invisible = InvisibleTextScanner()
            return self._piguard, self._invisible

    def scan(self, text: str, *, is_approval_reply: bool = False) -> None:
        """Scan one user message. Raise ``SecurityRejectionError`` if rejected.

        When ``is_approval_reply`` is True AND ``_is_pure_approval`` matches,
        the PIGuard scan is bypassed. Short affirmatives like "Approved.
        Execute the plan." reliably score > 0.99 on PIGuard even though
        they are benign in our domain. The bypass uses a strict whitelist
        of one or two concatenated approval words — enough headroom for
        legitimate researcher phrasing, no headroom for attacker prose.
        """
        if is_approval_reply and _is_pure_approval(text):
            return
        piguard, invisible = self._ensure_initialised()
        piguard_name = "PIGuardScanner"
        invisible_name = "InvisibleTextScanner"
        _, valid, score = piguard.scan(text)
        if not valid:
            logger.warning(
                "Input rejected by security scanner",
                scanner=piguard_name,
                risk_score=score,
            )
            raise SecurityRejectionError(piguard_name, score)
        _, visible_valid, visible_score = invisible.scan(text)
        if not visible_valid:
            logger.warning(
                "Input rejected by security scanner",
                scanner=invisible_name,
                risk_score=visible_score,
            )
            raise SecurityRejectionError(invisible_name, visible_score)


_scanner = UserInputScanner()


async def scan_user_input(text: str, *, is_approval_reply: bool = False) -> None:
    """Offload the CPU-bound scan to a thread so the event loop stays free."""
    await asyncio.to_thread(_scanner.scan, text, is_approval_reply=is_approval_reply)


__all__ = [
    "SecurityRejectionError",
    "UserInputScanner",
    "scan_user_input",
]
