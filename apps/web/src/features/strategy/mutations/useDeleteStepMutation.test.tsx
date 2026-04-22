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
  toast: { error: toastErrorMock, warning: vi.fn(), success: vi.fn() },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { useDeleteStepMutation } from "./useDeleteStepMutation";

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

describe("useDeleteStepMutation", () => {
  it("removes the step from store on mutate", async () => {
    const strategy = makeStrategy([
      step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }),
      step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }),
    ]);
    useStrategyStore.getState().setStrategy(strategy);
    pushConversationMock.mockResolvedValueOnce({
      ...strategy,
      steps: [strategy.steps[1]!],
      rootStepId: "s2",
    });

    const { result } = renderHook(() => useDeleteStepMutation());

    let p: Promise<unknown> | undefined;
    act(() => {
      p = result.current.mutateAsync({ stepId: "s1" });
    });
    expect(useStrategyStore.getState().strategy?.steps).toHaveLength(1);
    expect(useStrategyStore.getState().strategy?.steps[0]?.id).toBe("s2");
    await act(async () => {
      await p;
    });
  });

  it("re-adds step on error", async () => {
    const strategy = makeStrategy([
      step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }),
      step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }),
    ]);
    useStrategyStore.getState().setStrategy(strategy);
    pushConversationMock.mockRejectedValueOnce(new Error("boom"));

    const { result } = renderHook(() => useDeleteStepMutation());

    await act(async () => {
      await expect(
        result.current.mutateAsync({ stepId: "s1" }),
      ).rejects.toThrow("boom");
    });
    await waitFor(() => {
      expect(useStrategyStore.getState().strategy?.steps).toHaveLength(2);
      const ids = useStrategyStore
        .getState()
        .strategy?.steps.map((s) => s.id)
        .sort();
      expect(ids).toEqual(["s1", "s2"]);
    });
  });

  it("cascades to dependent steps (combine downstream of removed primary)", async () => {
    // s1, s2 → combine c1 (primary=s1, secondary=s2)
    const strategy = makeStrategy([
      step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }),
      step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }),
      step({
        id: "c1",
        displayName: "Combine",
        primaryInputStepId: "s1",
        secondaryInputStepId: "s2",
        operator: "INTERSECT",
        recordType: "gene",
      }),
    ]);
    useStrategyStore.getState().setStrategy(strategy);

    // Server response just echoes back the optimistic state for this assertion.
    pushConversationMock.mockImplementationOnce((_id, args) => {
      // The pushed AST after cascade should have only s2 as root (s1 + c1 gone).
      expect(args.strategyAst.root.id).toBe("s2");
      return Promise.resolve({
        ...strategy,
        steps: [strategy.steps[1]!],
        rootStepId: "s2",
      });
    });

    const { result } = renderHook(() => useDeleteStepMutation());

    let p: Promise<unknown> | undefined;
    act(() => {
      p = result.current.mutateAsync({ stepId: "s1" });
    });
    // Optimistic: s1 removed; combine c1 (which depended on s1) also removed.
    const optimisticIds = useStrategyStore
      .getState()
      .strategy?.steps.map((s) => s.id)
      .sort();
    expect(optimisticIds).toEqual(["s2"]);
    await act(async () => {
      await p;
    });
    expect(pushConversationMock).toHaveBeenCalledTimes(1);
  });
});
