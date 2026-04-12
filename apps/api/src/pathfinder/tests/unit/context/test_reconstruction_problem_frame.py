"""Regression tests for reconstructing scoping problem frames."""

import json

from pathfinder.ai.context.reconstruction import reconstruct_history
from pathfinder.platform.types import JSONObject


def test_reconstruct_history_extracts_latest_problem_frame() -> None:
    messages: list[JSONObject] = [
        {"role": "user", "content": "find transporters"},
        {
            "role": "assistant",
            "content": "Framed.",
            "toolCalls": [
                {
                    "id": "tc1",
                    "name": "set_problem_frame",
                    "arguments": {},
                    "result": json.dumps({
                        "problemFrame": {
                            "userGoal": "find transporters",
                            "interpretedGoal": "Identify likely membrane transporters",
                            "organismScope": "P. vivax",
                            "recordType": "transcript",
                            "readyForWdkDiscovery": True,
                            "confidence": 0.85,
                        }
                    }),
                }
            ],
        },
    ]

    reconstructed = reconstruct_history(messages)

    assert reconstructed.problem_frame is not None
    assert reconstructed.problem_frame.interpreted_goal == (
        "Identify likely membrane transporters"
    )
    assert reconstructed.problem_frame.ready_for_wdk_discovery is True
