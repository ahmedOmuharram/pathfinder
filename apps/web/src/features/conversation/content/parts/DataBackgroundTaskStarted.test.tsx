/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

import { DataBackgroundTaskStarted } from "./DataBackgroundTaskStarted";
import { streamTypedEvents } from "@/lib/sse/typedEventStream";
import type { TaskEventChunk } from "./taskLiveState";

vi.mock("next/navigation", () => ({
  usePathname: () => "/plasmodb/conversation/conv-1",
}));

vi.mock("@/lib/sse/typedEventStream", () => ({
  streamTypedEvents: vi.fn(),
}));

const mockedStream = vi.mocked(streamTypedEvents);

function setStream(chunks: TaskEventChunk[]): void {
  mockedStream.mockImplementation(() => {
    async function* gen(): AsyncGenerator<TaskEventChunk> {
      await Promise.resolve();
      for (const chunk of chunks) yield chunk;
    }
    return gen();
  });
}

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const STARTED = {
  taskId: "t1",
  toolName: "run_control_tests_on_step",
  estimatedDurationSeconds: 120,
} as const;

describe("DataBackgroundTaskStarted", () => {
  beforeEach(() => {
    setStream([]);
  });

  it("humanizes the tool name and rounds the duration up to whole minutes", () => {
    renderWithClient(<DataBackgroundTaskStarted data={STARTED} />);
    const card = screen.getByTestId("data-background-task-started");
    expect(card).toHaveTextContent("Run control tests");
    expect(card).toHaveTextContent("~2 min");

    renderWithClient(
      <DataBackgroundTaskStarted
        data={{ ...STARTED, estimatedDurationSeconds: 200 }}
      />,
    );
    expect(screen.getAllByTestId("data-background-task-started")[1]).toHaveTextContent(
      "~4 min",
    );
  });

  it("drives the progress bar width from the streamed percent (0.6 → 60%)", async () => {
    setStream([
      {
        type: "custom",
        kind: "data-task-progress",
        data: { taskId: "t1", percent: 0.6, message: "Comparing controls" },
      },
    ]);
    renderWithClient(<DataBackgroundTaskStarted data={STARTED} />);
    await screen.findByText("Comparing controls");
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByTestId("progress-bar-fill")).toHaveStyle({ width: "60%" });
  });

  it("replaces progress with a success completion and removes the progress bar", async () => {
    setStream([
      {
        type: "custom",
        kind: "data-task-progress",
        data: { taskId: "t1", percent: 0.6, message: "Comparing controls" },
      },
      { type: "custom", kind: "data-task-completed", data: { taskId: "t1", status: "success" } },
    ]);
    renderWithClient(<DataBackgroundTaskStarted data={STARTED} />);
    const completed = await screen.findByTestId("data-task-completed");
    expect(completed).toHaveTextContent("Task completed");
    await waitFor(() => {
      expect(screen.queryAllByTestId("progress-bar-fill")).toHaveLength(0);
    });
    expect(screen.queryByText("Comparing controls")).toBeNull();
  });

  it("renders a failed completion with the worker's error text", async () => {
    setStream([
      {
        type: "custom",
        kind: "data-task-completed",
        data: { taskId: "t1", status: "failed", error: "WDK rejected the search" },
      },
    ]);
    renderWithClient(<DataBackgroundTaskStarted data={STARTED} />);
    const completed = await screen.findByTestId("data-task-completed");
    expect(completed).toHaveTextContent("Task failed");
    expect(completed).toHaveTextContent("WDK rejected the search");
  });

  it("shows one lane per fan-out variant with each variant's latest percent", async () => {
    setStream([
      {
        type: "custom",
        kind: "data-task-progress",
        data: {
          taskId: "t1",
          percent: 0.3,
          message: "Trial 1/3",
          toolSpecific: { variantId: "v1" },
        },
      },
      {
        type: "custom",
        kind: "data-task-progress",
        data: {
          taskId: "t1",
          percent: 0.5,
          message: "Variant B running",
          toolSpecific: { variantId: "v2" },
        },
      },
      {
        type: "custom",
        kind: "data-task-progress",
        data: {
          taskId: "t1",
          percent: 0.9,
          message: "v1 best so far",
          toolSpecific: { variantId: "v1" },
        },
      },
    ]);
    renderWithClient(
      <DataBackgroundTaskStarted
        data={{ ...STARTED, toolName: "optimize_search_parameters" }}
      />,
    );
    const lanes = await screen.findAllByTestId("variant-lane");
    expect(lanes).toHaveLength(2);

    const v1 = lanes.find((l) => within(l).queryByText("v1 best so far") !== null);
    const v2 = lanes.find((l) => within(l).queryByText("Variant B running") !== null);
    expect(v1).toBeDefined();
    expect(v2).toBeDefined();

    expect(within(v1!).getByText("90%")).toBeInTheDocument();
    expect(within(v1!).getByTestId("progress-bar-fill")).toHaveStyle({ width: "90%" });
    expect(within(v1!).queryByText("30%")).toBeNull();
    expect(within(v2!).getByText("50%")).toBeInTheDocument();
    expect(within(v2!).getByTestId("progress-bar-fill")).toHaveStyle({ width: "50%" });
  });
});
