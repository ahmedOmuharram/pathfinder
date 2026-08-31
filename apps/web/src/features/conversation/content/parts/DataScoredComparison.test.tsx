/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";

import type { ScoredComparison } from "@pathfinder/shared";

import { DataScoredComparison } from "./DataScoredComparison";

const SCORED: ScoredComparison = {
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
      mcc: 0.82,
      f1: 0.9,
      precision: 0.9,
      sensitivity: 0.9,
      balancedAccuracy: 0.95,
      experimentId: "exp_b",
      error: null,
    },
  ],
};

describe("DataScoredComparison figure", () => {
  it("captions the figure with the variant count and the winning score", () => {
    render(<DataScoredComparison data={SCORED} />);
    expect(screen.getByTestId("figure-caption").textContent).toBe(
      "2 variants, winner strict at 0.82",
    );
  });

  it("captions a wholly failed scoring as a failure, not as a missing winner", () => {
    render(
      <DataScoredComparison
        data={{
          ...SCORED,
          winnerLabel: null,
          variants: SCORED.variants.map((v) => ({ ...v, error: "boom", mcc: null })),
        }}
      />,
    );
    expect(screen.getByTestId("figure-caption").textContent).toBe(
      "scoring failed for 2 of 2 variants",
    );
  });

  it("says so in the caption when nothing scored", () => {
    render(<DataScoredComparison data={{ ...SCORED, winnerLabel: null }} />);
    expect(screen.getByTestId("figure-caption").textContent).toBe(
      "2 variants, no winner",
    );
  });

  it("titles the figure Scored variants", () => {
    render(<DataScoredComparison data={SCORED} />);
    expect(screen.getByText("Scored variants").tagName).toBe("FIGCAPTION");
  });

  it("separates itself with a hairline, never with a card", () => {
    render(<DataScoredComparison data={SCORED} />);
    expect(screen.getByTestId("figure").className.split(/\s+/)).toEqual([
      "my-6",
      "border-t",
      "border-border/60",
      "pt-4",
    ]);
    expect(screen.getByTestId("data-scored-comparison").className).not.toMatch(
      /\bborder\b|\brounded-md\b|\bbg-card\b/,
    );
  });
});

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

  it("names the failure as a failed scoring, not as a bare failure", () => {
    render(
      <DataScoredComparison
        data={{
          objective: "mcc",
          winnerLabel: null,
          variants: [
            {
              label: "top 20%",
              searchName: "SA",
              mcc: null,
              f1: null,
              precision: null,
              sensitivity: null,
              balancedAccuracy: null,
              experimentId: null,
              error: "parameters.channel: Input should be a valid string",
              controlHits: ["PF3D7_1116700"],
            },
          ],
        }}
      />,
    );
    expect(
      screen.getByText(
        "scoring failed: parameters.channel: Input should be a valid string",
      ),
    ).toBeInTheDocument();
  });

  it("lists the control ids a variant contains", () => {
    render(
      <DataScoredComparison
        data={{
          objective: "mcc",
          winnerLabel: null,
          variants: [
            {
              label: "top 20%",
              searchName: "SA",
              mcc: null,
              f1: null,
              precision: null,
              sensitivity: null,
              balancedAccuracy: null,
              experimentId: null,
              error: "scoring blew up",
              controlHits: ["PF3D7_1116700", "PF3D7_0507500"],
            },
            {
              label: "top 5%",
              searchName: "SB",
              mcc: null,
              f1: null,
              precision: null,
              sensitivity: null,
              balancedAccuracy: null,
              experimentId: null,
              error: "scoring blew up",
              controlHits: [],
            },
          ],
        }}
      />,
    );
    expect(
      screen.getByText("contains PF3D7_1116700, PF3D7_0507500"),
    ).toBeInTheDocument();
    expect(screen.getByText("contains none of the control genes")).toBeInTheDocument();
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
