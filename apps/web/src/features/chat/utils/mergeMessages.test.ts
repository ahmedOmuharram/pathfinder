import { describe, expect, it } from "vitest";
import type { AssistantMessage, Message, UserMessage } from "@pathfinder/shared";
import { mergeMessages } from "./mergeMessages";

function assertAssistant(msg: Message): asserts msg is AssistantMessage {
  if (msg.role !== "assistant") throw new Error(`Expected assistant, got ${msg.role}`);
}

function userMsg(content: string, extra?: Partial<Omit<UserMessage, "role">>): UserMessage {
  return { role: "user", content, timestamp: new Date().toISOString(), ...extra };
}

function assistantMsg(content: string, extra?: Partial<Omit<AssistantMessage, "role">>): AssistantMessage {
  return { role: "assistant", content, timestamp: new Date().toISOString(), ...extra };
}

describe("mergeMessages", () => {
  it("returns incoming when current is empty", () => {
    const incoming: Message[] = [userMsg("hi"), assistantMsg("hello")];
    expect(mergeMessages([], incoming)).toEqual(incoming);
  });

  it("returns current when incoming is empty", () => {
    const current: Message[] = [userMsg("hi")];
    expect(mergeMessages(current, [])).toBe(current);
  });

  it("returns current when incoming is shorter (streaming in progress)", () => {
    const current: Message[] = [userMsg("hi"), assistantMsg("thinking...")];
    const incoming: Message[] = [userMsg("hi")]; // server hasn't seen assistant msg yet
    expect(mergeMessages(current, incoming)).toBe(current);
  });

  it("merges incoming when it has equal length", () => {
    const current: Message[] = [userMsg("hi"), assistantMsg("hello")];
    const incoming: Message[] = [userMsg("hi"), assistantMsg("hello")];
    const result = mergeMessages(current, incoming);
    expect(result.length).toBe(2);
  });

  it("preserves local-only toolCalls when server content matches", () => {
    const localToolCalls = [{ id: "t1", name: "search", arguments: { q: "abc" } }];
    const current: Message[] = [
      userMsg("hi"),
      assistantMsg("hello", { toolCalls: localToolCalls }),
    ];
    const incoming: Message[] = [userMsg("hi"), assistantMsg("hello")];
    const result = mergeMessages(current, incoming);
    assertAssistant(result[1]!);
    expect(result[1]!.toolCalls).toEqual(localToolCalls);
  });

  it("preserves local-only reasoning when server content matches", () => {
    const current: Message[] = [
      userMsg("hi"),
      assistantMsg("answer", { reasoning: "Step 1..." }),
    ];
    const incoming: Message[] = [userMsg("hi"), assistantMsg("answer")];
    const result = mergeMessages(current, incoming);
    assertAssistant(result[1]!);
    expect(result[1]!.reasoning).toBe("Step 1...");
  });

  it("prefers server data when both local and server have values", () => {
    const current: Message[] = [assistantMsg("hello", { reasoning: "local" })];
    const incoming: Message[] = [assistantMsg("hello", { reasoning: "server" })];
    const result = mergeMessages(current, incoming);
    assertAssistant(result[0]!);
    expect(result[0]!.reasoning).toBe("server");
  });

  it("handles refresh after streaming: server has all messages, current is empty", () => {
    // After page refresh, current is [] and server has the full history
    const serverMessages: Message[] = [
      userMsg("analyze genes"),
      assistantMsg("Here are the results", {
        toolCalls: [{ id: "t1", name: "search", arguments: {} }],
        citations: [{ id: "c1", title: "Paper", source: "web" }],
      }),
    ];
    const result = mergeMessages([], serverMessages);
    expect(result).toEqual(serverMessages);
    assertAssistant(result[1]!);
    expect(result[1]!.toolCalls).toHaveLength(1);
    expect(result[1]!.citations).toHaveLength(1);
  });

  it("handles switch-back scenario: messages from previous session merged correctly", () => {
    // User was on convo A, switched to B, switched back to A
    // On switch back, current is [] (cleared by reset), incoming has A's full history
    const history: Message[] = [
      userMsg("first question"),
      assistantMsg("first answer"),
      userMsg("second question"),
      assistantMsg("second answer"),
    ];
    const result = mergeMessages([], history);
    expect(result).toEqual(history);
    expect(result).toHaveLength(4);
  });

  it("does not lose messages when incoming is longer than current", () => {
    // Server has more messages than local (e.g. another tab sent a message)
    const current: Message[] = [userMsg("hi"), assistantMsg("hello")];
    const incoming: Message[] = [
      userMsg("hi"),
      assistantMsg("hello"),
      userMsg("follow up"),
      assistantMsg("response"),
    ];
    const result = mergeMessages(current, incoming);
    expect(result).toHaveLength(4);
  });

  it("preserves subKaniActivity from local when not on server", () => {
    const activity = { calls: { task1: [] }, status: { task1: "done" } };
    const current: Message[] = [assistantMsg("result", { subKaniActivity: activity })];
    const incoming: Message[] = [assistantMsg("result")];
    const result = mergeMessages(current, incoming);
    assertAssistant(result[0]!);
    expect(result[0]!.subKaniActivity).toEqual(activity);
  });
});
