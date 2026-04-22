from __future__ import annotations

import pytest

from pathfinder.ai.conversation.approval import (
    ApprovalDecision,
    classify_approval_reply,
)


@pytest.mark.parametrize(
    "text",
    [
        "yes",
        "Yes",
        "YES",
        "yes.",
        "yes!",
        "yep",
        "yeah",
        "ya",
        "ok",
        "okay",
        "Okay.",
        "sure",
        "fine",
        "approved",
        "approve",
        "Approved.",
        "go",
        "go ahead",
        "proceed",
        "Proceed.",
        "continue",
        "do it",
        "Do it.",
        "run it",
        "execute it",
        "Execute the plan",
        "launch",
        "launch it",
        "sounds good",
        "Sounds good.",
        "looks good",
        "Looks good!",
        "confirm",
        "confirmed",
        "accept",
        "accepted",
        "perfect",
        "great",
        "nice",
    ],
)
def test_approved_phrases(text: str) -> None:
    assert classify_approval_reply(text) == ApprovalDecision.APPROVED


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "no",
        "nope",
        "cancel",
        "stop",
        "reject",
        "change step 3 to use Plasmodium vivax",
        "actually, make the EST threshold 80%",
        "wait, who is the intended audience?",
        "I want to add another filter",
        "hmm, not sure yet",
        "looks good but change the title",
    ],
)
def test_denied_phrases(text: str) -> None:
    assert classify_approval_reply(text) == ApprovalDecision.DENIED
