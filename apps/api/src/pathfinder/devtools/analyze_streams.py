"""Analyze Redis streams — tool call sequences, phases, errors, token usage."""

import asyncio
import json

from redis.asyncio import Redis


async def analyze() -> None:
    redis = Redis(host="redis", port=6379, db=0)

    keys = await redis.keys("stream:*")
    recent: list[tuple[int, str, int]] = []
    for key in keys:
        length = await redis.xlen(key)
        if length > 20:
            last = await redis.xrevrange(key, count=1)
            if last:
                ts = int(last[0][0].decode().split("-")[0])
                recent.append((ts, key.decode(), length))
    recent.sort(reverse=True)

    for _ts, key, length in recent[:2]:
        print(f"\n{'=' * 60}")
        print(f"Stream: {key} ({length} entries)")
        print(f"{'=' * 60}")

        entries = await redis.xrange(key)
        turn = 0
        for _entry_id, fields in entries:
            event_type = fields.get(b"type", b"").decode()

            if event_type == "message_start":
                turn += 1
                print(f"\n--- Turn {turn} ---")

            if event_type == "user_message":
                data = json.loads(fields[b"data"])
                content = data.get("content", "")
                safe = content[:60].replace("\n", " ")
                print(f"  USER: {safe}...")

            if event_type == "tool_call_start":
                data = json.loads(fields[b"data"])
                name = data.get("name", "?")
                args = data.get("arguments", {})
                arg_keys = list(args.keys()) if isinstance(args, dict) else []
                print(f"  CALL: {name}({', '.join(arg_keys)})")

            if event_type == "tool_call_end":
                data = json.loads(fields[b"data"])
                result_str = data.get("result", "")
                result_len = len(result_str)
                is_error = (
                    "error" in result_str.lower()[:50]
                    or "DISCOVERY_REQUIRED" in result_str
                    or "VALIDATION_ERROR" in result_str
                )
                is_slim = result_str.startswith("ok:")
                status = "SLIM" if is_slim else ("ERROR" if is_error else "OK")
                print(f"    -> {status} ({result_len:,} chars)")

            if event_type == "assistant_message":
                data = json.loads(fields[b"data"])
                content = data.get("content", "")
                safe = content[:80].replace("\n", " ")
                print(f"  ASST: {safe}...")

            if event_type == "message_end":
                data = json.loads(fields[b"data"])
                prompt = data.get("promptTokens", 0)
                tools = data.get("toolCallCount", 0)
                llm_calls = data.get("llmCallCount", 0)
                cost = data.get("estimatedCostUsd", 0)
                print(
                    f"  END: prompt={prompt:,} tools={tools}"
                    f" llm_calls={llm_calls} cost=${cost:.2f}"
                )

    await redis.aclose()


asyncio.run(analyze())
