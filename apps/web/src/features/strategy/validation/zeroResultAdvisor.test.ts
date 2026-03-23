import { describe, expect, it } from "vitest";
import type { Step } from "@pathfinder/shared";
import { CombineOperator } from "@pathfinder/shared";
import { getZeroResultSuggestions } from "./zeroResultAdvisor";

// ---------------------------------------------------------------------------
// Helper: build a minimal Step with the required fields populated
// ---------------------------------------------------------------------------

function makeSearchStep(overrides?: Partial<Step>): Step {
  return {
    id: "s1",
    displayName: "Gene search",
    searchName: "GenesByKeyword",
    isBuilt: false,
    isFiltered: false,
    ...overrides,
  };
}

function makeTransformStep(overrides?: Partial<Step>): Step {
  return {
    id: "t1",
    displayName: "Transform step",
    searchName: "GenesByOrthology",
    primaryInputStepId: "s1",
    isBuilt: false,
    isFiltered: false,
    ...overrides,
  };
}

function makeCombineStep(
  operator: (typeof CombineOperator)[keyof typeof CombineOperator],
  overrides?: Partial<Step>,
): Step {
  return {
    id: "c1",
    displayName: "Combine step",
    primaryInputStepId: "s1",
    secondaryInputStepId: "s2",
    operator,
    isBuilt: false,
    isFiltered: false,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// getZeroResultSuggestions
// ---------------------------------------------------------------------------
describe("getZeroResultSuggestions", () => {
  // ----- universal suggestions -----
  describe("universal suggestions", () => {
    it("always includes the two broad suggestions", () => {
      const suggestions = getZeroResultSuggestions(makeSearchStep());
      expect(suggestions[0]).toContain("Relax overly strict parameters");
      expect(suggestions[1]).toContain("Verify organism");
    });
  });

  // ----- search steps -----
  describe("search steps", () => {
    it("suggests trying alternative search", () => {
      const suggestions = getZeroResultSuggestions(makeSearchStep());
      expect(suggestions).toContainEqual(expect.stringContaining("alternative search"));
    });

    it("does NOT include combine-specific suggestions", () => {
      const suggestions = getZeroResultSuggestions(makeSearchStep());
      const joined = suggestions.join(" ");
      expect(joined).not.toContain("INTERSECT");
      expect(joined).not.toContain("MINUS");
      expect(joined).not.toContain("both input steps");
    });

    it("does NOT include transform-specific suggestions", () => {
      const suggestions = getZeroResultSuggestions(makeSearchStep());
      const joined = suggestions.join(" ");
      expect(joined).not.toContain("upstream");
      expect(joined).not.toContain("orthology transform");
    });

    it("returns at most 5 suggestions", () => {
      const suggestions = getZeroResultSuggestions(makeSearchStep());
      expect(suggestions.length).toBeLessThanOrEqual(5);
    });
  });

  // ----- transform steps -----
  describe("transform steps", () => {
    it("suggests fixing upstream or adjusting transform params", () => {
      const suggestions = getZeroResultSuggestions(makeTransformStep());
      expect(suggestions).toContainEqual(expect.stringContaining("input step is zero"));
    });

    it("suggests orthology transform", () => {
      const suggestions = getZeroResultSuggestions(makeTransformStep());
      expect(suggestions).toContainEqual(
        expect.stringContaining("orthology transform"),
      );
    });

    it("does NOT include search-specific suggestions", () => {
      const suggestions = getZeroResultSuggestions(makeTransformStep());
      const joined = suggestions.join(" ");
      expect(joined).not.toContain("alternative search");
    });
  });

  // ----- combine steps -----
  describe("combine steps", () => {
    it("always suggests checking both inputs are non-zero", () => {
      const suggestions = getZeroResultSuggestions(
        makeCombineStep(CombineOperator.UNION),
      );
      expect(suggestions).toContainEqual(
        expect.stringContaining("both input steps are non-zero"),
      );
    });

    describe("INTERSECT operator", () => {
      it("suggests changing to UNION", () => {
        const suggestions = getZeroResultSuggestions(
          makeCombineStep(CombineOperator.INTERSECT),
        );
        expect(suggestions).toContainEqual(expect.stringContaining("change INTERSECT"));
      });
    });

    describe("MINUS / LONLY / RMINUS / RONLY operators", () => {
      for (const op of [
        CombineOperator.MINUS,
        CombineOperator.LONLY,
        CombineOperator.RMINUS,
        CombineOperator.RONLY,
      ] as const) {
        it(`suggests verifying MINUS direction for ${op}`, () => {
          const suggestions = getZeroResultSuggestions(makeCombineStep(op));
          expect(suggestions).toContainEqual(
            expect.stringContaining("verify MINUS direction"),
          );
        });
      }
    });

    describe("COLOCATE operator", () => {
      it("suggests increasing distance and verifying feature types", () => {
        const suggestions = getZeroResultSuggestions(
          makeCombineStep(CombineOperator.COLOCATE),
        );
        expect(suggestions).toContainEqual(
          expect.stringContaining("increase upstream/downstream"),
        );
      });
    });

    describe("UNION operator", () => {
      it("does NOT include INTERSECT or MINUS-specific suggestions", () => {
        const suggestions = getZeroResultSuggestions(
          makeCombineStep(CombineOperator.UNION),
        );
        const joined = suggestions.join(" ");
        expect(joined).not.toContain("change INTERSECT");
        expect(joined).not.toContain("verify MINUS direction");
        expect(joined).not.toContain("increase upstream/downstream");
      });
    });
  });

  // ----- edge cases -----
  describe("edge cases", () => {
    it("treats step with kind='combine' but no operator as combine", () => {
      const step: Step = {
        id: "c1",
        displayName: "Combine",
        kind: "combine",
        primaryInputStepId: "s1",
        secondaryInputStepId: "s2",
        isBuilt: false,
        isFiltered: false,
      };
      const suggestions = getZeroResultSuggestions(step);
      // Should include "both input steps" combine generic advice
      expect(suggestions).toContainEqual(
        expect.stringContaining("both input steps are non-zero"),
      );
    });

    it("returns at most 5 suggestions even for combine steps", () => {
      const suggestions = getZeroResultSuggestions(
        makeCombineStep(CombineOperator.INTERSECT),
      );
      expect(suggestions.length).toBeLessThanOrEqual(5);
    });

    it("step with explicit kind='search' overrides inference", () => {
      const step: Step = {
        id: "s1",
        displayName: "Explicit search",
        kind: "search",
        searchName: "GenesByKeyword",
        isBuilt: false,
        isFiltered: false,
      };
      const suggestions = getZeroResultSuggestions(step);
      expect(suggestions).toContainEqual(expect.stringContaining("alternative search"));
    });

    it("step with explicit kind='transform' overrides inference", () => {
      const step: Step = {
        id: "t1",
        displayName: "Explicit transform",
        kind: "transform",
        searchName: "GenesByOrthology",
        primaryInputStepId: "s1",
        isBuilt: false,
        isFiltered: false,
      };
      const suggestions = getZeroResultSuggestions(step);
      expect(suggestions).toContainEqual(
        expect.stringContaining("orthology transform"),
      );
    });
  });
});
