import { describe, expect, it } from "vitest";

import { isTransportChunk } from "./replayChunks";

describe("isTransportChunk", () => {
  it("drops the user message the event log keeps for snapshots", () => {
    // The client already holds the user's own message. The schema the
    // transport parses with has no such chunk, so passing it on kills the
    // stream before the assistant's first token.
    expect(isTransportChunk('{"type":"user-message","message":{"id":"m1"}}')).toBe(
      false,
    );
  });

  it("keeps the chunk that opens an assistant message", () => {
    expect(isTransportChunk('{"type":"start","messageId":"m2"}')).toBe(true);
  });

  it("keeps text deltas", () => {
    expect(isTransportChunk('{"type":"text-delta","id":"t","delta":"hi"}')).toBe(true);
  });

  it("keeps data parts", () => {
    expect(isTransportChunk('{"type":"data-turn-usage","data":{}}')).toBe(true);
  });

  it("keeps the terminator", () => {
    expect(isTransportChunk("[DONE]")).toBe(true);
  });

  it("keeps anything it cannot parse, so the schema still judges it", () => {
    expect(isTransportChunk("not json")).toBe(true);
  });
});
