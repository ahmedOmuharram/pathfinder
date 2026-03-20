import { describe, expect, it } from "vitest";
import type { Message } from "@pathfinder/shared";
import { mergeMessages } from "./mergeMessages";

function msg(
  role: "user" | "assistant",
  content: string,
  extra?: Partial<Message>,
): Message {
  return { role, content, timestamp: new Date().toISOString(), ...extra };
}

describe("mergeMessages", () => {
  it("returns incoming when current is empty", () => {
    const incoming = [msg("user", "hi"), msg("assistant", "hello")];
    expect(mergeMessages([], incoming)).toEqual(incoming);
  });

  it("returns current when incoming is empty", () => {
    const current = [msg("user", "hi")];
    expect(mergeMessages(current, [])).toBe(current);
  });

  it("returns current when incoming is shorter (streaming in progress)", () => {
    const current = [msg("user", "hi"), msg("assistant", "thinking...")];
    const incoming = [msg("user", "hi")]; // server hasn't seen assistant msg yet
    expect(mergeMessages(current, incoming)).toBe(current);
  });

  it("merges incoming when it has equal length", () => {
    const current = [msg("user", "hi"), msg("assistant", "hello")];
    const incoming = [msg("user", "hi"), msg("assistant", "hello")];
    const result = mergeMessages(current, incoming);
    expect(result.length).toBe(2);
  });

  it("preserves local-only toolCalls when server content matches", () => {
    const localToolCalls = [{ id: "t1", name: "search", arguments: { q: "abc" } }];
    const current = [
      msg("user", "hi"),
      msg("assistant", "hello", { toolCalls: localToolCalls }),
    ];
    const incoming = [msg("user", "hi"), msg("assistant", "hello")];
    const result = mergeMessages(current, incoming);
    expect(result[1]!.toolCalls).toEqual(localToolCalls);
  });

  it("preserves local-only reasoning when server content matches", () => {
    const current = [
      msg("user", "hi"),
      msg("assistant", "answer", { reasoning: "Step 1..." }),
    ];
    const incoming = [msg("user", "hi"), msg("assistant", "answer")];
    const result = mergeMessages(current, incoming);
    expect(result[1]!.reasoning).toBe("Step 1...");
  });

  it("prefers server data when both local and server have values", () => {
    const current = [msg("assistant", "hello", { reasoning: "local" })];
    const incoming = [msg("assistant", "hello", { reasoning: "server" })];
    const result = mergeMessages(current, incoming);
    expect(result[0]!.reasoning).toBe("server");
  });

  it("handles refresh after streaming: server has all messages, current is empty", () => {
    // After page refresh, current is [] and server has the full history
    const serverMessages = [
      msg("user", "analyze genes"),
      msg("assistant", "Here are the results", {
        toolCalls: [{ id: "t1", name: "search", arguments: {} }],
        citations: [{ id: "c1", title: "Paper", source: "web" }],
      }),
    ];
    const result = mergeMessages([], serverMessages);
    expect(result).toEqual(serverMessages);
    expect(result[1]!.toolCalls).toHaveLength(1);
    expect(result[1]!.citations).toHaveLength(1);
  });

  it("handles switch-back scenario: messages from previous session merged correctly", () => {
    // User was on convo A, switched to B, switched back to A
    // On switch back, current is [] (cleared by reset), incoming has A's full history
    const history = [
      msg("user", "first question"),
      msg("assistant", "first answer"),
      msg("user", "second question"),
      msg("assistant", "second answer"),
    ];
    const result = mergeMessages([], history);
    expect(result).toEqual(history);
    expect(result).toHaveLength(4);
  });

  it("does not lose messages when incoming is longer than current", () => {
    // Server has more messages than local (e.g. another tab sent a message)
    const current = [msg("user", "hi"), msg("assistant", "hello")];
    const incoming = [
      msg("user", "hi"),
      msg("assistant", "hello"),
      msg("user", "follow up"),
      msg("assistant", "response"),
    ];
    const result = mergeMessages(current, incoming);
    expect(result).toHaveLength(4);
  });

  it("preserves subKaniActivity from local when not on server", () => {
    const activity = { calls: { task1: [] }, status: { task1: "done" } };
    const current = [msg("assistant", "result", { subKaniActivity: activity })];
    const incoming = [msg("assistant", "result")];
    const result = mergeMessages(current, incoming);
    expect(result[0]!.subKaniActivity).toEqual(activity);
  });
});
