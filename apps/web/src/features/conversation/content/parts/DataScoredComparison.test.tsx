/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { DataScoredComparison } from "./DataScoredComparison";

describe("DataScoredComparison", () => {
  it("ranks variants, flags the winner, and shows metrics", () => {
    render(
      <DataScoredComparison
        data={{
          objective: "mcc",
          winnerLabel: "strict",
          variants: [
            {
              label: "lenient",
              searchName: "SA",
              mcc: 0.6,
              f1: 0.8,
              precision: 0.8,
              sensitivity: 0.8,
              balancedAccuracy: 0.8,
              experimentId: "exp_a",
              error: null,
            },
            {
              label: "strict",
              searchName: "SB",
              mcc: 1.0,
              f1: 0.9,
              precision: 0.9,
              sensitivity: 0.9,
              balancedAccuracy: 0.95,
              experimentId: "exp_b",
              error: null,
            },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("data-scored-comparison")).toBeInTheDocument();
    expect(screen.getByText(/ranked by mcc/i)).toBeInTheDocument();
    // winner badge appears exactly once, on the strict row
    const winner = screen.getByText("winner");
    expect(winner).toBeInTheDocument();
    expect(screen.getByText(/MCC 1\.00/)).toBeInTheDocument();
    expect(screen.getByText(/MCC 0\.60/)).toBeInTheDocument();
  });

  it("shows a failed variant's error and no metrics", () => {
    render(
      <DataScoredComparison
        data={{
          objective: "mcc",
          winnerLabel: "ok",
          variants: [
            {
              label: "ok",
              searchName: "SA",
              mcc: 0.5,
              f1: 0.5,
              precision: 0.5,
              sensitivity: 0.5,
              balancedAccuracy: 0.5,
              experimentId: "exp_a",
              error: null,
            },
            {
              label: "broken",
              searchName: "SB",
              mcc: null,
              f1: null,
              precision: null,
              sensitivity: null,
              balancedAccuracy: null,
              experimentId: null,
              error: "WDK exploded",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/failed: WDK exploded/i)).toBeInTheDocument();
  });

  it("does not render a winner badge when no variant scored", () => {
    render(
      <DataScoredComparison
        data={{
          objective: "mcc",
          winnerLabel: null,
          variants: [
            {
              label: "broken",
              searchName: "SB",
              mcc: null,
              f1: null,
              precision: null,
              sensitivity: null,
              balancedAccuracy: null,
              experimentId: null,
              error: "boom",
            },
          ],
        }}
      />,
    );
    const card = screen.getByTestId("data-scored-comparison");
    expect(within(card).queryByText("winner")).not.toBeInTheDocument();
  });
});
