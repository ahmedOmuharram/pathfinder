import { describe, it, expect, vi, beforeEach } from "vitest";
import type { PlanningArtifact, Strategy } from "@pathfinder/shared";
import { applyPlanningArtifactAction } from "./applyPlanningArtifactAction";
import type { ApplyPlanningArtifactDeps } from "./applyPlanningArtifactAction";

vi.mock("@/lib/api/strategies", () => ({
  updateStrategy: vi.fn(),
  getStrategy: vi.fn(),
}));

import { updateStrategy, getStrategy } from "@/lib/api/strategies";

const mockUpdateStrategy = vi.mocked(updateStrategy);
const mockGetStrategy = vi.mocked(getStrategy);

function makeStrategy(overrides?: Partial<Strategy>): Strategy {
  return {
    id: "strat-1",
    name: "Test",
    siteId: "plasmodb",
    recordType: "transcript",
    steps: [],
    rootStepId: null,
    isSaved: false,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeDeps(): ApplyPlanningArtifactDeps {
  return {
    setStrategy: vi.fn(),
    setStrategyMeta: vi.fn(),
  };
}

const VALID_PLAN: NonNullable<PlanningArtifact["proposedStrategyPlan"]> = {
  recordType: "transcript",
  root: { searchName: "GenesByTaxon", parameters: { organism: "P. falciparum" } },
};

function makeArtifact(proposedStrategyPlan?: PlanningArtifact["proposedStrategyPlan"]): PlanningArtifact {
  return {
    id: "art-1",
    title: "Test Artifact",
    summaryMarkdown: "summary",
    assumptions: [],
    createdAt: "2026-01-01T00:00:00Z",
    ...(proposedStrategyPlan !== undefined ? { proposedStrategyPlan } : {}),
  };
}

describe("applyPlanningArtifactAction", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns false when proposedStrategyPlan is null", async () => {
    const deps = makeDeps();
    const result = await applyPlanningArtifactAction("strat-1", makeArtifact(null), deps);
    expect(result).toBe(false);
    expect(mockUpdateStrategy).not.toHaveBeenCalled();
  });

  it("returns false when proposedStrategyPlan is missing", async () => {
    const deps = makeDeps();
    const result = await applyPlanningArtifactAction("strat-1", makeArtifact(), deps);
    expect(result).toBe(false);
    expect(mockUpdateStrategy).not.toHaveBeenCalled();
  });

  it("applies valid plan, updates strategy, and returns true", async () => {
    const fullStrategy = makeStrategy({
      name: "Applied",
      description: "desc",
      recordType: "transcript",
      siteId: "plasmodb",
    });
    mockUpdateStrategy.mockResolvedValue(fullStrategy);
    mockGetStrategy.mockResolvedValue(fullStrategy);

    const deps = makeDeps();
    const result = await applyPlanningArtifactAction("strat-1", makeArtifact(VALID_PLAN), deps);

    expect(result).toBe(true);
    expect(mockUpdateStrategy).toHaveBeenCalledWith("strat-1", {
      plan: VALID_PLAN,
    });
    expect(mockGetStrategy).toHaveBeenCalledWith("strat-1");
    expect(deps.setStrategy).toHaveBeenCalledWith(fullStrategy);
    expect(deps.setStrategyMeta).toHaveBeenCalledWith({
      name: "Applied",
      description: "desc",
      recordType: "transcript",
      siteId: "plasmodb",
    });
  });
});
