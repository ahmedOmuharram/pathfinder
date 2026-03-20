// @vitest-environment jsdom
/**
 * Tests for useWorkbenchChatAutoTrigger — auto-interprets on first open
 * when no conversation history exists.
 */

import { describe, expect, it, vi, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useWorkbenchChatAutoTrigger } from "./useWorkbenchChatAutoTrigger";

describe("useWorkbenchChatAutoTrigger", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("calls sendMessage when history is loaded and empty", () => {
    const sendMessage = vi.fn();
    renderHook(() =>
      useWorkbenchChatAutoTrigger({
        experimentId: "exp-1",
        historyLoaded: true,
        messageCount: 0,
        streaming: false,
        sendMessage,
      }),
    );

    expect(sendMessage).toHaveBeenCalledTimes(1);
    expect(sendMessage).toHaveBeenCalledWith(expect.stringContaining("interpret"));
  });

  it("does not call sendMessage when experimentId is null", () => {
    const sendMessage = vi.fn();
    renderHook(() =>
      useWorkbenchChatAutoTrigger({
        experimentId: null,
        historyLoaded: true,
        messageCount: 0,
        streaming: false,
        sendMessage,
      }),
    );

    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("does not call sendMessage when history is not loaded", () => {
    const sendMessage = vi.fn();
    renderHook(() =>
      useWorkbenchChatAutoTrigger({
        experimentId: "exp-1",
        historyLoaded: false,
        messageCount: 0,
        streaming: false,
        sendMessage,
      }),
    );

    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("does not call sendMessage when messages already exist", () => {
    const sendMessage = vi.fn();
    renderHook(() =>
      useWorkbenchChatAutoTrigger({
        experimentId: "exp-1",
        historyLoaded: true,
        messageCount: 2,
        streaming: false,
        sendMessage,
      }),
    );

    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("does not call sendMessage when already streaming", () => {
    const sendMessage = vi.fn();
    renderHook(() =>
      useWorkbenchChatAutoTrigger({
        experimentId: "exp-1",
        historyLoaded: true,
        messageCount: 0,
        streaming: true,
        sendMessage,
      }),
    );

    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("does not trigger twice for the same experimentId", () => {
    const sendMessage = vi.fn();
    const { rerender } = renderHook((props) => useWorkbenchChatAutoTrigger(props), {
      initialProps: {
        experimentId: "exp-1",
        historyLoaded: true,
        messageCount: 0,
        streaming: false,
        sendMessage,
      },
    });

    expect(sendMessage).toHaveBeenCalledTimes(1);

    // Re-render with same experimentId — should not trigger again
    rerender({
      experimentId: "exp-1",
      historyLoaded: true,
      messageCount: 1, // now has messages from the first trigger
      streaming: false,
      sendMessage,
    });

    expect(sendMessage).toHaveBeenCalledTimes(1);
  });
});
