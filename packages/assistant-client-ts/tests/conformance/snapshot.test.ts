import { describe, expect, it } from "vitest";

import { HANDLED_ENVELOPE_KINDS, reduceSnapshot } from "../../src/core/snapshot.ts";

function userEnvelope(id: string, text: string): unknown {
  return {
    type: "user-message",
    message: { id, role: "user", parts: [{ type: "text", text }] },
  };
}

describe("section 5.3, envelopes rebuild the prompt side", () => {
  it("names the three kinds the document defines", () => {
    expect([...HANDLED_ENVELOPE_KINDS].sort()).toEqual([
      "assistant-message",
      "system-message",
      "user-message",
    ]);
  });

  it("takes a user message from the log as a whole message", () => {
    expect(reduceSnapshot([userEnvelope("u1", "hello")])).toEqual([
      { id: "u1", role: "user", parts: [{ type: "text", text: "hello" }] },
    ]);
  });

  it("takes a system message from the log", () => {
    const envelope = {
      type: "system-message",
      message: { id: "s1", role: "system", parts: [{ type: "text", text: "rules" }] },
    };

    expect(reduceSnapshot([envelope])).toEqual([
      { id: "s1", role: "system", parts: [{ type: "text", text: "rules" }] },
    ]);
  });

  it("takes a whole assistant message that was not built from deltas", () => {
    const envelope = {
      type: "assistant-message",
      message: {
        id: "a1",
        role: "assistant",
        parts: [{ type: "text", text: "canned" }],
      },
    };

    expect(reduceSnapshot([envelope])).toEqual([
      { id: "a1", role: "assistant", parts: [{ type: "text", text: "canned" }] },
    ]);
  });

  it("never lets an envelope reach the turn reducer", () => {
    const messages = reduceSnapshot([
      { type: "start", messageId: "a1" },
      { type: "text-start", id: "t" },
      { type: "text-delta", id: "t", delta: "hi" },
      {
        type: "assistant-message",
        message: { id: "a2", role: "assistant", parts: [] },
      },
    ]);

    expect(messages).toHaveLength(2);
    expect(messages[0]?.parts).toEqual([
      { type: "text", text: "hi", state: "streaming" },
    ]);
    expect(messages[1]?.id).toBe("a2");
  });
});

describe("section 2, a snapshot rebuilds the whole conversation", () => {
  it("orders prompts and answers as the log holds them", () => {
    const messages = reduceSnapshot([
      userEnvelope("u1", "first"),
      { type: "start", messageId: "a1" },
      { type: "text-start", id: "t1" },
      { type: "text-delta", id: "t1", delta: "one" },
      { type: "text-end", id: "t1" },
      { type: "finish", finishReason: "stop" },
      { type: "done" },
      userEnvelope("u2", "second"),
      { type: "start", messageId: "a2" },
      { type: "text-start", id: "t2" },
      { type: "text-delta", id: "t2", delta: "two" },
      { type: "text-end", id: "t2" },
      { type: "finish", finishReason: "stop" },
      { type: "done" },
    ]);

    expect(messages.map((message) => message.id)).toEqual(["u1", "a1", "u2", "a2"]);
    expect(messages[1]?.parts).toEqual([{ type: "text", text: "one", state: "done" }]);
    expect(messages[3]?.parts).toEqual([{ type: "text", text: "two", state: "done" }]);
  });

  it("splits two assistant messages that share no envelope between them", () => {
    const messages = reduceSnapshot([
      { type: "start", messageId: "a1" },
      { type: "text-start", id: "t1" },
      { type: "text-delta", id: "t1", delta: "one" },
      { type: "start", messageId: "a2" },
      { type: "text-start", id: "t2" },
      { type: "text-delta", id: "t2", delta: "two" },
    ]);

    expect(messages.map((message) => message.id)).toEqual(["a1", "a2"]);
  });

  it("keeps a status part on the assistant message it precedes", () => {
    const messages = reduceSnapshot([
      { type: "data-turn-status", data: { label: "Queued" } },
      { type: "start", messageId: "a1" },
      { type: "text-start", id: "t1" },
      { type: "text-delta", id: "t1", delta: "hello" },
      { type: "text-end", id: "t1" },
      { type: "finish", finishReason: "stop" },
      { type: "done" },
    ]);

    expect(messages).toEqual([
      {
        id: "a1",
        role: "assistant",
        errors: [],
        aborted: false,
        finishReason: "stop",
        parts: [
          { type: "data-turn-status", data: { label: "Queued" } },
          { type: "text", text: "hello", state: "done" },
        ],
      },
    ]);
  });

  it("reads an empty log as an empty conversation", () => {
    expect(reduceSnapshot([])).toEqual([]);
  });

  it("ignores an entry that is not a chunk", () => {
    expect(reduceSnapshot([null, 7, "text", { noType: true }])).toEqual([]);
  });

  it("drops an envelope that carries no message", () => {
    expect(reduceSnapshot([{ type: "user-message" }])).toEqual([]);
  });
});
