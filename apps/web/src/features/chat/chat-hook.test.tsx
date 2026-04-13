// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";

import { useChatSession } from "./chat-hook";

describe("useChatSession", () => {
  it("exposes useChat return values", () => {
    const { result } = renderHook(() => useChatSession("chat-abc", "strategy"));
    expect(result.current).toHaveProperty("messages");
    expect(result.current).toHaveProperty("status");
    expect(result.current).toHaveProperty("sendMessage");
    expect(result.current).toHaveProperty("stop");
    expect(result.current).toHaveProperty("regenerate");
    expect(result.current.messages).toEqual([]);
  });
});
