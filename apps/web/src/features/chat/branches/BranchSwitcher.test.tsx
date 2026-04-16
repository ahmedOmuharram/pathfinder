/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import { BranchSwitcher } from "./BranchSwitcher";

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
    ],
    edges: [],
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <NuqsTestingAdapter>{ui}</NuqsTestingAdapter>
    </QueryClientProvider>,
  );
}

describe("BranchSwitcher", () => {
  it("renders the toggle button with checkpoint count", async () => {
    renderWithProviders(<BranchSwitcher chatId="c1" />);
    expect(
      screen.getByRole("button", { name: /branches/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText("1")).toBeInTheDocument();
  });

  it("opens the panel when toggle is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<BranchSwitcher chatId="c1" />);

    await user.click(screen.getByRole("button", { name: /branches/i }));
    expect(screen.getByTestId("branch-tree")).toBeInTheDocument();
  });

  it("closes the panel when toggle is clicked again", async () => {
    const user = userEvent.setup();
    renderWithProviders(<BranchSwitcher chatId="c1" />);

    const toggle = screen.getByRole("button", { name: /branches/i });
    await user.click(toggle);
    expect(screen.getByTestId("branch-tree")).toBeInTheDocument();

    await user.click(toggle);
    expect(screen.queryByTestId("branch-tree")).not.toBeInTheDocument();
  });
});
