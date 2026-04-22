/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Strategy, Step } from "@pathfinder/shared";

const pushConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", () => ({
  pushConversation: pushConversationMock,
}));

const toastErrorMock = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: {
    error: toastErrorMock,
    warning: vi.fn(),
    success: vi.fn(),
  },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { useDuplicateStepMutation } from "./useDuplicateStepMutation";

function step(partial: Partial<Step> & { id: string; displayName: string }): Step {
  return { isBuilt: false, isFiltered: false, ...partial } as Step;
}

function makeStrategy(steps: Step[]): Strategy {
  return {
    id: "strategy-1",
    name: "Test",
    siteId: "plasmodb",
    recordType: "gene",
    steps,
    rootStepId: steps[steps.length - 1]?.id ?? null,
    isSaved: false,
    description: null,
    wdkStrategyId: null,
    wdkUrl: null,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  };
}

beforeEach(() => {
  useStrategyStore.getState().clear();
  useStrategyStore.setState({ graphValidationStatus: {} });
  pushConversationMock.mockReset();
  toastErrorMock.mockReset();
});

describe("useDuplicateStepMutation", () => {
  it("duplicates a single root search step into a sibling combined via INTERSECT", async () => {
    const strategy = makeStrategy([
      step({
        id: "s1",
        displayName: "Genes by taxon",
        kind: "search",
        searchName: "GenesByTaxon",
        recordType: "gene",
        parameters: { organism: "Plasmodium" },
      }),
    ]);
    useStrategyStore.getState().setStrategy(strategy);

    pushConversationMock.mockImplementationOnce(async (_id, args) => {
      // Server echoes back optimistic strategy.
      return {
        ...strategy,
        steps: useStrategyStore.getState().strategy?.steps ?? [],
        rootStepId: args.strategyAst.root.id,
      };
    });

    const { result } = renderHook(() => useDuplicateStepMutation());

    let p: Promise<unknown> | undefined;
    act(() => {
      p = result.current.mutateAsync({ stepId: "s1" });
    });

    // Optimistic: 3 steps — original, duplicate, combine.
    const optimisticSteps = useStrategyStore.getState().strategy?.steps ?? [];
    expect(optimisticSteps).toHaveLength(3);
    const dup = optimisticSteps.find(
      (s) => s.id !== "s1" && s.searchName === "GenesByTaxon",
    );
    expect(dup).toBeDefined();
    expect(dup?.parameters).toEqual({ organism: "Plasmodium" });
    expect(dup?.id).not.toBe("s1");

    const combine = optimisticSteps.find(
      (s) => s.primaryInputStepId != null && s.secondaryInputStepId != null,
    );
    expect(combine).toBeDefined();
    expect(combine?.operator).toBe("INTERSECT");
    expect(combine?.primaryInputStepId).toBe("s1");
    expect(combine?.secondaryInputStepId).toBe(dup?.id);

    await act(async () => {
      await p;
    });

    expect(pushConversationMock).toHaveBeenCalledTimes(1);
  });

  it("rolls back the duplicate on push error", async () => {
    const strategy = makeStrategy([
      step({
        id: "s1",
        displayName: "Genes by taxon",
        kind: "search",
        searchName: "GenesByTaxon",
        recordType: "gene",
      }),
    ]);
    useStrategyStore.getState().setStrategy(strategy);
    pushConversationMock.mockRejectedValueOnce(new Error("boom"));

    const { result } = renderHook(() => useDuplicateStepMutation());

    await act(async () => {
      await expect(
        result.current.mutateAsync({ stepId: "s1" }),
      ).rejects.toThrow("boom");
    });

    await waitFor(() => {
      const steps = useStrategyStore.getState().strategy?.steps ?? [];
      expect(steps).toHaveLength(1);
      expect(steps[0]?.id).toBe("s1");
    });
    expect(toastErrorMock).toHaveBeenCalled();
  });

  it("when source is non-root, rewires the parent input to point at the new combine", async () => {
    const strategy = makeStrategy([
      step({
        id: "s1",
        displayName: "Genes by taxon",
        kind: "search",
        searchName: "GenesByTaxon",
        recordType: "gene",
      }),
      step({
        id: "t1",
        displayName: "Transformed",
        kind: "transform",
        searchName: "GenesByOrtholog",
        recordType: "gene",
        primaryInputStepId: "s1",
      }),
    ]);
    useStrategyStore.getState().setStrategy(strategy);

    pushConversationMock.mockImplementationOnce(async () => ({
      ...strategy,
      steps: useStrategyStore.getState().strategy?.steps ?? [],
    }));

    const { result } = renderHook(() => useDuplicateStepMutation());

    let p: Promise<unknown> | undefined;
    act(() => {
      p = result.current.mutateAsync({ stepId: "s1" });
    });

    const steps = useStrategyStore.getState().strategy?.steps ?? [];
    // s1, dup of s1, new combine, t1 (rewired to combine)
    expect(steps).toHaveLength(4);
    const t1 = steps.find((s) => s.id === "t1");
    const combine = steps.find(
      (s) => s.primaryInputStepId === "s1" && s.secondaryInputStepId != null,
    );
    expect(combine).toBeDefined();
    expect(t1?.primaryInputStepId).toBe(combine?.id);

    await act(async () => {
      await p;
    });
    expect(pushConversationMock).toHaveBeenCalledTimes(1);
  });
});
