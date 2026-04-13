// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import type { PlanArtifact } from "@pathfinder/shared";

import { StrategyPlanCard } from "./StrategyPlanCard";

const PLAN: PlanArtifact = {
  planId: "plan-123",
  rationale: "Find host genes regulated by parasite invasion.",
  steps: [
    { order: 1, searchName: "GenesByText", rationale: "Seed gene set" },
    { order: 2, searchName: "GenesByGoTerm", rationale: "Filter by GO term" },
  ],
};

describe("StrategyPlanCard", () => {
  it("renders an ordered list with each planned step's searchName and rationale", () => {
    render(<StrategyPlanCard plan={PLAN} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    const [first, second] = items;
    expect(first?.textContent).toContain("GenesByText");
    expect(first?.textContent).toContain("Seed gene set");
    expect(second?.textContent).toContain("GenesByGoTerm");
    expect(second?.textContent).toContain("Filter by GO term");
  });

  it("renders the plan rationale and tags the card with the plan id", () => {
    const { container } = render(<StrategyPlanCard plan={PLAN} />);

    expect(
      screen.getByText(/Find host genes regulated by parasite invasion\./),
    ).toBeTruthy();
    const card = container.querySelector(".strategy-plan-card");
    expect(card).toBeTruthy();
    expect(card?.getAttribute("data-plan-id")).toBe("plan-123");
  });
});
