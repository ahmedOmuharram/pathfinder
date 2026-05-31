/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataTaskProgress } from "./DataTaskProgress";

describe("DataTaskProgress", () => {
  it("renders progress message and percentage", () => {
    render(
      <DataTaskProgress
        data={{
          taskId: "t1",
          percent: 0.65,
          message: "Running trial 13/20",
        }}
      />,
    );
    expect(screen.getByTestId("data-task-progress")).toBeInTheDocument();
    expect(screen.getByText("Running trial 13/20")).toBeInTheDocument();
    expect(screen.getByText("65%")).toBeInTheDocument();
  });

  it("renders single lane when no variantId", () => {
    render(
      <DataTaskProgress
        data={{
          taskId: "t1",
          percent: 0.5,
          message: "Processing step",
        }}
      />,
    );
    expect(screen.getByTestId("data-task-progress")).toBeInTheDocument();
    expect(screen.queryAllByTestId("variant-lane")).toHaveLength(0);
  });

  it("renders one lane per variantId", () => {
    render(
      <DataTaskProgress
        data={{
          taskId: "t1",
          percent: 0.3,
          message: "Running variant v1",
          toolSpecific: { variantId: "v1" },
        }}
        variants={
          new Map([
            [
              "v1",
              {
                taskId: "t1",
                percent: 0.3,
                message: "Running variant v1",
                toolSpecific: { variantId: "v1" },
              },
            ],
            [
              "v2",
              {
                taskId: "t1",
                percent: 0.6,
                message: "Running variant v2",
                toolSpecific: { variantId: "v2" },
              },
            ],
            [
              "v3",
              {
                taskId: "t1",
                percent: 0.9,
                message: "Running variant v3",
                toolSpecific: { variantId: "v3" },
              },
            ],
          ])
        }
      />,
    );
    expect(screen.getAllByTestId("variant-lane")).toHaveLength(3);
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("v3")).toBeInTheDocument();
  });

  it("progress bar width reflects percent", () => {
    render(
      <DataTaskProgress
        data={{
          taskId: "t1",
          percent: 0.42,
          message: "Almost halfway",
        }}
      />,
    );
    const bar = screen
      .getByTestId("data-task-progress")
      .querySelector("[data-testid='progress-bar-fill']");
    expect(bar).toHaveStyle({ width: "42%" });
  });

  it("progress bar width reflects percent in variant lanes", () => {
    render(
      <DataTaskProgress
        data={{
          taskId: "t1",
          percent: 0.75,
          message: "Running variant v1",
          toolSpecific: { variantId: "v1" },
        }}
        variants={
          new Map([
            [
              "v1",
              {
                taskId: "t1",
                percent: 0.75,
                message: "Running variant v1",
                toolSpecific: { variantId: "v1" },
              },
            ],
          ])
        }
      />,
    );
    const lane = screen.getByTestId("variant-lane");
    const bar = lane.querySelector("[data-testid='progress-bar-fill']");
    expect(bar).toHaveStyle({ width: "75%" });
  });
});
