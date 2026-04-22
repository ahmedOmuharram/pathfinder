from __future__ import annotations

import re
from enum import StrEnum


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"


_APPROVAL_WORDS = frozenset(
    {
        "yes", "yep", "yeah", "ya", "yup",
        "ok", "okay", "okey", "sure", "fine",
        "approved", "approve",
        "go", "proceed", "continue",
        "do", "run", "execute", "launch",
        "confirm", "confirmed", "accept", "accepted",
        "perfect", "great", "nice", "sounds", "looks",
    },
)

_DENIAL_WORDS = frozenset(
    {
        "no", "nope", "nah",
        "cancel", "stop", "abort", "skip",
        "reject", "rejected", "deny", "denied",
        "dont", "not",
        "wait", "hold",
        "but", "however", "except", "although",
        "change", "modify", "edit", "update",
        "add", "remove", "delete", "replace", "swap",
        "instead",
    },
)

_NON_AUTHORING_FILLER = frozenset(
    {
        "please", "just", "and", "then", "so", "the", "a", "it",
        "plan", "step", "steps",
    },
)

_WORD_RE = re.compile(r"[a-z']+")
_MAX_REPLY_WORDS = 8


def classify_approval_reply(text: str) -> ApprovalDecision:
    """Classify a user reply to a pending approval.

    Short affirmative phrases -> APPROVED. Anything that looks like
    change requests, new instructions, or denials -> DENIED, so the
    resuming agent sees a denial and can re-plan against the user's text.
    """
    stripped = text.strip()
    if not stripped:
        return ApprovalDecision.DENIED
    words = _WORD_RE.findall(stripped.lower())
    if not words:
        return ApprovalDecision.DENIED
    word_set = set(words)
    if word_set & _DENIAL_WORDS:
        return ApprovalDecision.DENIED
    content_words = [w for w in words if w not in _NON_AUTHORING_FILLER]
    if len(content_words) > _MAX_REPLY_WORDS:
        return ApprovalDecision.DENIED
    if not word_set & _APPROVAL_WORDS:
        return ApprovalDecision.DENIED
    return ApprovalDecision.APPROVED
