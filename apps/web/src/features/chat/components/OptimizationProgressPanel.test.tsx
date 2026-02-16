// @vitest-environment jsdom
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within, fireEvent } from "@testing-library/react";
import type { OptimizationProgressData, OptimizationTrial } from "@pathfinder/shared";
import { OptimizationProgressPanel } from "@/features/chat/components/OptimizationProgressPanel";

vi.mock("recharts", () => {
  const Box = ({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) => (
    <div data-props={JSON.stringify(props)}>{children}</div>
  );
  return {
    ResponsiveContainer: Box,
    LineChart: ({ children, data }: React.PropsWithChildren<{ data?: unknown[] }>) => (
      <div data-testid="line-chart" data-points={String(data?.length ?? 0)}>
        {children}
      </div>
    ),
    Line: Box,
    XAxis: (props: Record<string, unknown>) => (
      <div data-testid="x-axis-domain">{JSON.stringify(props.domain)}</div>
    ),
    YAxis: (props: Record<string, unknown>) => (
      <div data-testid="y-axis-domain">{JSON.stringify(props.domain)}</div>
    ),
    Tooltip: Box,
    CartesianGrid: Box,
    ReferenceArea: Box,
    ReferenceLine: Box,
  };
});

function trial(trialNumber: number, score: number): OptimizationTrial {
  return {
    trialNumber,
    parameters: { hard_floor: 0.1 * trialNumber },
    score,
    recall: 0.5,
    falsePositiveRate: 0.1,
    resultCount: 10,
    positiveHits: 5,
    negativeHits: 1,
    totalPositives: 10,
    totalNegatives: 10,
  };
}

function buildData(): OptimizationProgressData {
  return {
    optimizationId: "opt-1",
    status: "running",
    currentTrial: 5,
    totalTrials: 10,
    parameterSpace: [{ name: "hard_floor", type: "numeric" }],
    recentTrials: [trial(4, 0.61), trial(5, 0.66)],
    allTrials: [
      trial(1, 0.42),
      trial(2, 0.55),
      trial(3, 0.6),
      trial(4, 0.61),
      trial(5, 0.66),
    ],
    paretoFrontier: [trial(4, 0.61), trial(5, 0.66)],
  };
}

describe("OptimizationProgressPanel UI behavior", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders chart from all trials", () => {
    render(<OptimizationProgressPanel data={buildData()} />);
    expect(screen.getByTestId("line-chart").getAttribute("data-points")).toBe("5");
  });

  it("trial table is collapsed by default and expands on click", () => {
    render(<OptimizationProgressPanel data={buildData()} />);

    // Table should NOT be visible by default (collapsed)
    expect(screen.queryByRole("table")).toBeNull();

    // The "Recent trials" toggle button should be visible
    const toggleBtn = screen.getByText("Recent trials").closest("button")!;
    expect(toggleBtn).toBeTruthy();

    // Click to expand
    fireEvent.click(toggleBtn);

    // Now the table should be visible with recent trials only
    const table = screen.getByRole("table");
    const bodyRows = within(table).getAllByRole("row").slice(1);
    expect(bodyRows).toHaveLength(2);
  });

  it("shows trial count note when allTrials > recentTrials", () => {
    render(<OptimizationProgressPanel data={buildData()} />);
    expect(screen.getByText(/Showing last 2 of 5 trials/)).toBeTruthy();
  });

  it("does not render a standalone Pareto summary block", () => {
    render(<OptimizationProgressPanel data={buildData()} />);
    expect(screen.queryByText(/Pareto frontier/i)).toBeNull();
  });

  it("locks axes to expected domains", () => {
    render(<OptimizationProgressPanel data={buildData()} />);
    expect(screen.getByTestId("x-axis-domain").textContent).toBe("[0,10]");
    expect(screen.getByTestId("y-axis-domain").textContent).toBe("[0,1]");
  });

  it("chart container uses CSS containment to prevent resize", () => {
    const { container } = render(<OptimizationProgressPanel data={buildData()} />);
    const chartWrapper = container.querySelector("[style*='contain']") as HTMLElement;
    expect(chartWrapper).toBeTruthy();
    expect(chartWrapper.style.contain).toContain("size");
  });

  it("uses a fixed panel width so chart width does not change while writing", () => {
    const { container } = render(<OptimizationProgressPanel data={buildData()} />);
    const panel = container.querySelector(
      "[data-testid='optimization-panel']",
    ) as HTMLElement;
    expect(panel).toBeTruthy();
    expect(panel.className).toContain("w-[760px]");
  });
});
