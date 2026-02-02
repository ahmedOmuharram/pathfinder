import { describe, expect, it } from "vitest";
import { parseChatSSEEvent } from "./sse_events";

describe("parseChatSSEEvent", () => {
  it("parses known event type with JSON payload", () => {
    const evt = parseChatSSEEvent({
      type: "assistant_message",
      data: JSON.stringify({ content: "hi" }),
    });
    expect(evt.type).toBe("assistant_message");
    if (evt.type === "assistant_message") {
      expect(evt.data).toEqual({ content: "hi" });
    }
  });

  it("returns unknown for forward-compatible events", () => {
    const evt = parseChatSSEEvent({ type: "future_event", data: "x" });
    expect(evt.type).toBe("unknown");
    if (evt.type === "unknown") {
      expect(evt.rawType).toBe("future_event");
      expect(evt.data).toBe("x");
    }
  });
});

