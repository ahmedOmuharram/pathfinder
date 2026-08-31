/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { createTestWrapper } from "@/lib/query/testing";

const mockSystemReady = vi.hoisted(() => vi.fn());

vi.mock("@pathfinder/shared/generated/hooks/useSystemReady", () => ({
  systemReady: mockSystemReady,
  systemReadyQueryKey: () => [{ url: "/health/system" }] as const,
  systemReadyQueryOptions: () => ({
    queryKey: [{ url: "/health/system" }] as const,
    queryFn: mockSystemReady,
  }),
}));

async function renderGate() {
  const { SystemReadyGate } = await import("./SystemReadyGate");
  const { Wrapper } = createTestWrapper();
  return render(
    <Wrapper>
      <SystemReadyGate>
        <div data-testid="app-content">ready content</div>
      </SystemReadyGate>
    </Wrapper>,
  );
}

describe("SystemReadyGate", () => {
  beforeEach(() => {
    vi.resetModules();
    mockSystemReady.mockReset();
  });

  it("shows the startup screen while not ready, listing what is pending", async () => {
    mockSystemReady.mockResolvedValue({
      ready: false,
      apiReady: false,
      workerAlive: false,
      notReady: ["database"],
    });

    await renderGate();

    await waitFor(() => {
      expect(screen.getByText(/starting up/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/database/)).toBeInTheDocument();
    expect(screen.queryByTestId("app-content")).not.toBeInTheDocument();
  });

  it("renders the app behind a banner when only the worker is unresponsive", async () => {
    mockSystemReady.mockResolvedValue({
      ready: false,
      apiReady: true,
      workerAlive: false,
      notReady: ["worker"],
    });

    await renderGate();

    await waitFor(() => {
      expect(screen.getByTestId("app-content")).toBeInTheDocument();
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      /background service is not responding/i,
    );
    expect(screen.queryByText(/failed to start/i)).not.toBeInTheDocument();
  });

  it("keeps the fatal screen when a subsystem other than the worker is down", async () => {
    mockSystemReady.mockResolvedValue({
      ready: false,
      apiReady: false,
      workerAlive: true,
      notReady: ["database"],
    });

    await renderGate();

    await waitFor(() => {
      expect(screen.getByText(/starting up/i)).toBeInTheDocument();
    });
    expect(screen.queryByTestId("app-content")).not.toBeInTheDocument();
  });

  it("renders children once the system is ready", async () => {
    mockSystemReady.mockResolvedValue({
      ready: true,
      apiReady: true,
      workerAlive: true,
      notReady: [],
    });

    await renderGate();

    await waitFor(() => {
      expect(screen.getByTestId("app-content")).toBeInTheDocument();
    });
    expect(screen.queryByText(/starting up/i)).not.toBeInTheDocument();
  });
});
