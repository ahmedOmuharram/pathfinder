/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { UIMessage } from "ai";
import type { TaskCompleted, TaskProgressChunk } from "@pathfinder/shared";

import {
  ChatHelpersProvider,
  type ChatHelpers,
} from "../../runtime/chatHelpersContext";
import { DataBackgroundTaskStarted } from "./DataBackgroundTaskStarted";

vi.mock("next/navigation", () => ({
  usePathname: () => "/plasmodb/conversation/conv-1",
}));

const STARTED = {
  taskId: "t1",
  toolName: "run_control_tests_on_step",
  estimatedDurationSeconds: 120,
} as const;

function progressPart(data: TaskProgressChunk): UIMessage["parts"][number] {
  return { type: "data-task-progress", data } as UIMessage["parts"][number];
}

function completedPart(data: TaskCompleted): UIMessage["parts"][number] {
  return { type: "data-task-completed", data } as UIMessage["parts"][number];
}

function makeChat(
  parts: UIMessage["parts"][number][],
  resumeStream: () => Promise<void>,
  status: ChatHelpers["status"] = "ready",
): ChatHelpers {
  return {
    id: "conv-1",
    messages: [
      {
        id: "m1",
        role: "assistant",
        parts: [
          { type: "data-background-task-started", data: STARTED },
          ...parts,
        ] as UIMessage["parts"],
      },
    ],
    status,
    error: undefined,
    setMessages: () => {},
    sendMessage: async () => {},
    regenerate: async () => {},
    stop: async () => {},
    resumeStream,
    addToolResult: async () => {},
    addToolOutput: async () => {},
    addToolApprovalResponse: () => {},
    clearError: () => {},
  };
}

function renderCard(
  parts: UIMessage["parts"][number][],
  options: { resumeStream?: () => Promise<void>; status?: ChatHelpers["status"] } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const chat = makeChat(
    parts,
    options.resumeStream ?? (async () => {}),
    options.status ?? "ready",
  );
  const ui = (
    <QueryClientProvider client={client}>
      <ChatHelpersProvider value={chat}>
        <DataBackgroundTaskStarted data={STARTED} />
      </ChatHelpersProvider>
    </QueryClientProvider>
  );
  return { ...render(ui), ui };
}

describe("DataBackgroundTaskStarted", () => {
  it("humanizes the tool name and rounds the duration up to whole minutes", () => {
    renderCard([]);
    const card = screen.getByTestId("data-background-task-started");
    expect(card).toHaveTextContent("Run control tests");
    expect(card).toHaveTextContent("~2 min");
  });

  it("drives the progress bar from the message's own progress part", () => {
    renderCard([
      progressPart({ taskId: "t1", percent: 0.6, message: "Comparing controls" }),
    ]);
    expect(screen.getByText("Comparing controls")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByTestId("progress-bar-fill")).toHaveStyle({ width: "60%" });
  });

  it("replaces progress with a success completion and removes the progress bar", () => {
    renderCard([
      progressPart({ taskId: "t1", percent: 0.6, message: "Comparing controls" }),
      completedPart({ taskId: "t1", status: "success" }),
    ]);
    const completed = screen.getByTestId("data-task-completed");
    expect(completed).toHaveTextContent("Task completed");
    expect(screen.queryAllByTestId("progress-bar-fill")).toHaveLength(0);
    expect(screen.queryByText("Comparing controls")).toBeNull();
  });

  it("renders a failed completion with the worker's error text", () => {
    renderCard([
      completedPart({
        taskId: "t1",
        status: "failed",
        error: "WDK rejected the search",
      }),
    ]);
    const completed = screen.getByTestId("data-task-completed");
    expect(completed).toHaveTextContent("Task failed");
    expect(completed).toHaveTextContent("WDK rejected the search");
  });

  it("ignores parts that belong to another task", () => {
    renderCard([
      progressPart({ taskId: "other", percent: 0.9, message: "Not this task" }),
      completedPart({ taskId: "other", status: "success" }),
    ]);
    expect(screen.queryByText("Not this task")).toBeNull();
    expect(screen.queryByTestId("data-task-completed")).toBeNull();
  });

  it("reattaches the thread exactly once while the task is unfinished", async () => {
    const resumeStream = vi.fn(async () => {});
    const { rerender, ui } = renderCard([], { resumeStream });
    await waitFor(() => {
      expect(resumeStream).toHaveBeenCalledTimes(1);
    });
    rerender(ui);
    await waitFor(() => {
      expect(resumeStream).toHaveBeenCalledTimes(1);
    });
  });

  it("does not reattach while the suspending turn is still streaming", async () => {
    const resumeStream = vi.fn(async () => {});
    renderCard([], { resumeStream, status: "streaming" });
    await Promise.resolve();
    expect(resumeStream).not.toHaveBeenCalled();
  });

  it("renders a reloaded finished card without reattaching the thread", async () => {
    const resumeStream = vi.fn(async () => {});
    renderCard(
      [
        progressPart({ taskId: "t1", percent: 1, message: "Scoring" }),
        completedPart({ taskId: "t1", status: "success" }),
      ],
      { resumeStream },
    );
    expect(screen.getByTestId("data-task-completed")).toHaveTextContent(
      "Task completed",
    );
    await Promise.resolve();
    expect(resumeStream).not.toHaveBeenCalled();
  });
});
