/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import type { Strategy, Step } from "@pathfinder/shared";

const pushConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", () => ({
  pushConversation: pushConversationMock,
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), warning: vi.fn(), success: vi.fn() },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { useAddStepMutation } from "./useAddStepMutation";

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
});

describe("useAddStepMutation", () => {
  it("inserts a new step into the store with a client-generated id (empty -> first step)", async () => {
    const empty = makeStrategy([]);
    useStrategyStore.getState().setStrategy(empty);

    pushConversationMock.mockImplementationOnce((_id, args) => {
      return Promise.resolve({
        ...empty,
        steps: [
          {
            ...step({
              id: args.strategyAst.root.id,
              displayName: "New step",
              searchName: "GenesByTaxon",
              recordType: "gene",
            }),
            wdkStepId: 555,
          } as Step,
        ],
        rootStepId: args.strategyAst.root.id,
      });
    });

    const { result } = renderHook(() => useAddStepMutation());

    let p: Promise<unknown> | undefined;
    act(() => {
      p = result.current.mutateAsync({
        step: step({
          id: "added-1",
          displayName: "New step",
          searchName: "GenesByTaxon",
          recordType: "gene",
        }),
      });
    });

    // Optimistic: store now has the new step.
    const ids = useStrategyStore
      .getState()
      .strategy?.steps.map((s) => s.id);
    expect(ids).toEqual(["added-1"]);

    await act(async () => {
      await p;
    });

    // Server response replaces — the new step now has wdkStepId attached.
    const added = useStrategyStore
      .getState()
      .strategy?.steps.find((s) => s.id === "added-1");
    expect(added?.wdkStepId).toBe(555);
  });

  it("inserts a combine step that references existing inputs", async () => {
    const strategy = makeStrategy([
      step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }),
      step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }),
    ]);
    useStrategyStore.getState().setStrategy(strategy);

    pushConversationMock.mockImplementationOnce((_id, args) => {
      return Promise.resolve({
        ...strategy,
        steps: [
          ...strategy.steps,
          step({
            id: args.strategyAst.root.id,
            displayName: "Combine",
            primaryInputStepId: "s1",
            secondaryInputStepId: "s2",
            operator: "INTERSECT",
            recordType: "gene",
          }),
        ],
        rootStepId: args.strategyAst.root.id,
      });
    });

    const { result } = renderHook(() => useAddStepMutation());

    await act(async () => {
      await result.current.mutateAsync({
        step: step({
          id: "c1",
          displayName: "Combine",
          primaryInputStepId: "s1",
          secondaryInputStepId: "s2",
          operator: "INTERSECT",
          recordType: "gene",
        }),
      });
    });

    const c = useStrategyStore.getState().strategy?.steps.find((s) => s.id === "c1");
    expect(c?.operator).toBe("INTERSECT");
    expect(c?.primaryInputStepId).toBe("s1");
    expect(c?.secondaryInputStepId).toBe("s2");
  });
});
