/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import { BranchTree } from "./BranchTree";

vi.mock("@/lib/api/client", () => ({
  client: vi.fn().mockResolvedValue({
    data: [
      {
        checkpointId: "cp0",
        parentCheckpointId: null,
        threadId: "t1",
        source: "input",
        step: 0,
        node: "supervisor",
        createdAt: "",
      },
      {
        checkpointId: "cp1",
        parentCheckpointId: "cp0",
        threadId: "t1",
        source: "loop",
        step: 1,
        node: "scoping",
        createdAt: "",
      },
    ],
  }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("./layoutCheckpointTree", () => ({
  layoutCheckpointTree: vi.fn().mockResolvedValue({
    nodes: [
      {
        id: "cp0",
        type: "checkpointNode",
        position: { x: 0, y: 0 },
        data: {
          checkpointId: "cp0",
          parentCheckpointId: null,
          threadId: "t1",
          source: "input",
          step: 0,
          node: "supervisor",
          createdAt: "",
        },
      },
      {
        id: "cp1",
        type: "checkpointNode",
        position: { x: 0, y: 100 },
        data: {
          checkpointId: "cp1",
          parentCheckpointId: "cp0",
          threadId: "t1",
          source: "loop",
          step: 1,
          node: "scoping",
          createdAt: "",
        },
      },
    ],
    edges: [{ id: "cp0->cp1", source: "cp0", target: "cp1", type: "default" }],
  }),
}));

function renderWithProviders(
  ui: React.ReactElement,
  nuqsProps: Record<string, unknown> = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <NuqsTestingAdapter {...nuqsProps}>{ui}</NuqsTestingAdapter>
    </QueryClientProvider>,
  );
}

describe("BranchTree", () => {
  it("renders without crashing", async () => {
    renderWithProviders(<BranchTree chatId="chat-1" />);
    expect(await screen.findByText("supervisor")).toBeInTheDocument();
    expect(screen.getByText("scoping")).toBeInTheDocument();
  });

  it("updates URL state when a node is clicked", async () => {
    const user = userEvent.setup();
    const onUrlUpdate = vi.fn();
    renderWithProviders(<BranchTree chatId="chat-1" />, {
      onUrlUpdate,
      hasMemory: true,
    });

    await screen.findByText("scoping");
    const nodeWrapper = document.querySelector('[data-id="cp1"]');
    expect(nodeWrapper).not.toBeNull();
    await user.click(nodeWrapper!);

    expect(onUrlUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        queryString: expect.stringContaining("branch=cp1"),
      }),
    );
  });

  it("highlights the node matching the initial branch param", async () => {
    renderWithProviders(<BranchTree chatId="chat-1" />, {
      searchParams: { branch: "cp0" },
    });

    await screen.findByText("supervisor");
    const nodes = document.querySelectorAll("[data-branch-node]");
    expect(nodes.length).toBeGreaterThan(0);
  });
});
