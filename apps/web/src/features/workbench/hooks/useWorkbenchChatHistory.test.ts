// @vitest-environment jsdom
/**
 * Tests for useWorkbenchChatHistory — loads message history from the API
 * and transforms API responses into WorkbenchMessage[].
 */

import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const mockGetMessages = vi.hoisted(() => vi.fn());

vi.mock("../api/workbenchChatApi", () => ({
  getWorkbenchChatMessages: (...args: unknown[]) => mockGetMessages(...args),
}));

import { useWorkbenchChatHistory } from "./useWorkbenchChatHistory";

describe("useWorkbenchChatHistory", () => {
  beforeEach(() => {
    mockGetMessages.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads messages when experimentId is provided", async () => {
    mockGetMessages.mockResolvedValue([
      { role: "user", content: "hi", messageId: "m1" },
      { role: "assistant", content: "hello", messageId: "m2" },
    ]);

    const { result } = renderHook(() => useWorkbenchChatHistory("exp-1"));

    await waitFor(() => {
      expect(result.current.historyLoaded).toBe(true);
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toEqual(
      expect.objectContaining({ role: "user", content: "hi" }),
    );
  });

  it("filters out empty content messages", async () => {
    mockGetMessages.mockResolvedValue([
      { role: "user", content: "hi", messageId: "m1" },
      { role: "assistant", content: "", messageId: "m2" },
      { role: "assistant", content: "real response", messageId: "m3" },
    ]);

    const { result } = renderHook(() => useWorkbenchChatHistory("exp-1"));

    await waitFor(() => {
      expect(result.current.historyLoaded).toBe(true);
    });

    expect(result.current.messages).toHaveLength(2);
  });

  it("preserves toolCalls from loaded messages", async () => {
    const toolCalls = [{ id: "tc-1", name: "search_genes", result: "42" }];
    mockGetMessages.mockResolvedValue([
      { role: "assistant", content: "found", messageId: "m1", toolCalls },
    ]);

    const { result } = renderHook(() => useWorkbenchChatHistory("exp-1"));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(1);
    });

    expect(result.current.messages[0]?.toolCalls).toEqual(toolCalls);
  });

  it("preserves citations from loaded messages", async () => {
    const citations = [{ title: "Paper A", url: "https://example.com/a" }];
    mockGetMessages.mockResolvedValue([
      { role: "assistant", content: "Explanation", messageId: "m1", citations },
    ]);

    const { result } = renderHook(() => useWorkbenchChatHistory("exp-1"));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(1);
    });

    expect(result.current.messages[0]?.citations).toEqual(citations);
  });

  it("does not fetch when experimentId is null", async () => {
    const { result } = renderHook(() => useWorkbenchChatHistory(null));

    // Give effects time to run
    await new Promise<void>((r) => setTimeout(r, 50));

    expect(mockGetMessages).not.toHaveBeenCalled();
    // null === null -> historyLoaded is vacuously true (nothing to load)
    expect(result.current.historyLoaded).toBe(true);
  });

  it("marks historyLoaded even when fetch fails", async () => {
    mockGetMessages.mockRejectedValue(new Error("network error"));

    const { result } = renderHook(() => useWorkbenchChatHistory("exp-1"));

    await waitFor(() => {
      expect(result.current.historyLoaded).toBe(true);
    });

    expect(result.current.messages).toHaveLength(0);
  });
});
