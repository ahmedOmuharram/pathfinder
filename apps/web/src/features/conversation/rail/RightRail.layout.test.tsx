/**
 * @vitest-environment jsdom
 */
import type { UIMessage } from "ai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/plasmodb/conversation/conv-1",
}));

import { useLeftSidebarStore, useRightRailStore } from "@/state/useRightRailStore";
import { ChatHelpersProvider, type ChatHelpers } from "../runtime/chatHelpersContext";
import { RightRail } from "./RightRail";

function makeChat(messages: UIMessage[], id: string): ChatHelpers {
  return {
    id,
    messages,
    status: "ready",
    error: undefined,
    setMessages: () => {},
    sendMessage: async () => {},
    regenerate: async () => {},
    stop: async () => {},
    resumeStream: async () => {},
    addToolResult: async () => {},
    addToolOutput: async () => {},
    addToolApprovalResponse: () => {},
    clearError: () => {},
  };
}

function renderRail(conversationId: string, messages: UIMessage[]): void {
  render(
    <ChatHelpersProvider value={makeChat(messages, conversationId)}>
      <RightRail conversationId={conversationId} strategy={null} siteId="plasmodb" />
    </ChatHelpersProvider>,
  );
}

function setViewportWidth(width: number): void {
  window.innerWidth = width;
  window.innerHeight = 900;
}

const TASK_STARTED: UIMessage[] = [
  {
    id: "m1",
    role: "assistant",
    parts: [{ type: "data-background-task-started", data: {} }],
  },
];

beforeEach(() => {
  useRightRailStore.setState({
    openPanel: null,
    autoOpenedConversation: null,
    ledgerSeen: {},
    lastSeen: {},
  });
  useLeftSidebarStore.setState({ collapsed: false });
  setViewportWidth(1440);
});

describe("the rail badge is scoped to the open conversation", () => {
  it("raises no Tasks dot on a fresh conversation after another one ran a task", () => {
    renderRail("conv-1", TASK_STARTED);
    expect(screen.getByLabelText("Tasks has updates")).toBeInTheDocument();

    screen.getByLabelText("Open Tasks").click();
    expect(useRightRailStore.getState().lastSeen["conv-1"]?.taskCount).toBe(1);

    cleanup();
    renderRail("conv-2", []);
    expect(screen.queryByLabelText("Tasks has updates")).toBe(null);
  });
});

describe("the rail panel at a narrow viewport", () => {
  it("overlays the chat at 866px instead of squeezing it", () => {
    setViewportWidth(866);
    useRightRailStore.setState({ openPanel: "tasks" });
    renderRail("conv-1", []);
    expect(screen.getByTestId("rail-panel").getAttribute("data-overlay")).toBe("true");
    expect(screen.getByTestId("rail-panel").className).toContain("absolute");
  });

  it("keeps the panel in flow on a wide viewport", () => {
    setViewportWidth(1440);
    useRightRailStore.setState({ openPanel: "tasks" });
    renderRail("conv-1", []);
    expect(screen.getByTestId("rail-panel").getAttribute("data-overlay")).toBe("false");
    expect(screen.getByTestId("rail-panel").className).not.toContain("absolute");
  });
});
