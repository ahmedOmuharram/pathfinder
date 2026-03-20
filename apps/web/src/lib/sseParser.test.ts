import { describe, expect, it } from "vitest";
import { parseSSEChunk } from "./sseParser";

describe("parseSSEChunk", () => {
  // ── Happy-path ──────────────────────────────────────────────

  it("parses a single complete SSE frame with default event type", () => {
    const { events, rest } = parseSSEChunk("data: hello\n\n");
    expect(events).toEqual([{ type: "message", data: "hello" }]);
    expect(rest).toBe("");
  });

  it("parses a frame with an explicit event type", () => {
    const { events, rest } = parseSSEChunk("event: status\ndata: ok\n\n");
    expect(events).toEqual([{ type: "status", data: "ok" }]);
    expect(rest).toBe("");
  });

  it("parses a frame with an id field", () => {
    const { events } = parseSSEChunk("id: 42\ndata: payload\n\n");
    expect(events).toEqual([{ type: "message", data: "payload", id: "42" }]);
  });

  it("parses a frame with all three fields", () => {
    const { events } = parseSSEChunk('event: update\nid: abc\ndata: {"x":1}\n\n');
    expect(events).toEqual([{ type: "update", data: '{"x":1}', id: "abc" }]);
  });

  it("joins multiple data lines with newlines", () => {
    const { events } = parseSSEChunk("data: line1\ndata: line2\ndata: line3\n\n");
    expect(events[0]!.data).toBe("line1\nline2\nline3");
  });

  it("parses multiple frames in one chunk", () => {
    const chunk = "data: first\n\ndata: second\n\n";
    const { events, rest } = parseSSEChunk(chunk);
    expect(events).toHaveLength(2);
    expect(events[0]!.data).toBe("first");
    expect(events[1]!.data).toBe("second");
    expect(rest).toBe("");
  });

  // ── Leftover / incomplete buffer ───────────────────────────

  it("returns incomplete frame as rest", () => {
    const { events, rest } = parseSSEChunk("data: partial");
    expect(events).toHaveLength(0);
    expect(rest).toBe("data: partial");
  });

  it("returns trailing incomplete frame as rest after a complete one", () => {
    const { events, rest } = parseSSEChunk("data: done\n\ndata: pending");
    expect(events).toHaveLength(1);
    expect(events[0]!.data).toBe("done");
    expect(rest).toBe("data: pending");
  });

  // ── Comment lines and keep-alives ──────────────────────────

  it("drops SSE comment lines (starting with ':')", () => {
    const { events } = parseSSEChunk(": this is a comment\ndata: real\n\n");
    expect(events).toHaveLength(1);
    expect(events[0]!.data).toBe("real");
  });

  it("drops keep-alive frames with no data lines", () => {
    const { events } = parseSSEChunk(": keepalive\n\n");
    expect(events).toHaveLength(0);
  });

  it("drops frames that have only comment lines", () => {
    const { events } = parseSSEChunk(": comment1\n: comment2\n\n");
    expect(events).toHaveLength(0);
  });

  it("drops frames that consist only of an event type but no data", () => {
    const { events } = parseSSEChunk("event: heartbeat\n\n");
    expect(events).toHaveLength(0);
  });

  // ── Edge cases ─────────────────────────────────────────────

  it("handles empty string input", () => {
    const { events, rest } = parseSSEChunk("");
    expect(events).toHaveLength(0);
    expect(rest).toBe("");
  });

  it("handles \\r\\n line endings", () => {
    const { events } = parseSSEChunk("event: ev\r\ndata: d\r\n\r\n");
    expect(events).toEqual([{ type: "ev", data: "d" }]);
  });

  it("handles mixed \\r\\n and \\n line endings", () => {
    const { events } = parseSSEChunk("data: mixed\r\n\n");
    expect(events).toHaveLength(1);
    expect(events[0]!.data).toBe("mixed");
  });

  it("ignores blank parts (double blank lines)", () => {
    const { events } = parseSSEChunk("data: a\n\n\n\ndata: b\n\n");
    expect(events).toHaveLength(2);
    expect(events[0]!.data).toBe("a");
    expect(events[1]!.data).toBe("b");
  });

  it("trims whitespace from event type value", () => {
    const { events } = parseSSEChunk("event:  spaced  \ndata: x\n\n");
    expect(events[0]!.type).toBe("spaced");
  });

  it("trims leading whitespace from data value", () => {
    const { events } = parseSSEChunk("data:   padded\n\n");
    expect(events[0]!.data).toBe("padded");
  });

  it("trims whitespace from id value", () => {
    const { events } = parseSSEChunk("id:  ev-1  \ndata: x\n\n");
    expect(events[0]!.id).toBe("ev-1");
  });

  it("uses default event type when event: value is empty", () => {
    const { events } = parseSSEChunk("event:\ndata: fallback\n\n");
    expect(events[0]!.type).toBe("message");
  });

  it("ignores unknown field lines", () => {
    const { events } = parseSSEChunk("retry: 3000\ndata: val\n\n");
    expect(events).toHaveLength(1);
    expect(events[0]!.data).toBe("val");
  });

  it("handles data with colons in the value", () => {
    const { events } = parseSSEChunk('data: {"key":"value"}\n\n');
    expect(events[0]!.data).toBe('{"key":"value"}');
  });

  it("accumulates buffer across sequential calls", () => {
    const first = parseSSEChunk("data: hel");
    expect(first.events).toHaveLength(0);

    const second = parseSSEChunk(first.rest + "lo\n\n");
    expect(second.events).toHaveLength(1);
    expect(second.events[0]!.data).toBe("hello");
    expect(second.rest).toBe("");
  });
});
