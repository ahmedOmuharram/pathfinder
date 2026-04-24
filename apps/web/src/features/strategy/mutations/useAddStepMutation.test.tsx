/**
 * @vitest-environment jsdom
 */

import type * as ConversationsModule from "@/lib/api/conversations";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import type { Strategy, Step } from "@pathfinder/shared";

const pushConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual =
    await importOriginal<typeof ConversationsModule>();
  return { ...actual, pushConversation: pushConversationMock };
});

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), warning: vi.fn(), success: vi.fn() },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { useAddStepMutation } from "./useAddStepMutation";
import { makeQueryHarness } from "./__tests__/strategyTestUtils";

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
  it("inserts a new step into the cache with a client-generated id", async () => {
    const empty = makeStrategy([]);
    const harness = makeQueryHarness(empty);

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

    const { result } = renderHook(
      () => useAddStepMutation(empty.id),
      { wrapper: harness.wrapper },
    );

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

    const optimisticIds = harness.getStrategy(empty.id)?.steps.map((s) => s.id);
    expect(optimisticIds).toEqual(["added-1"]);

    await act(async () => {
      await p;
    });

    const added = harness
      .getStrategy(empty.id)
      ?.steps.find((s) => s.id === "added-1");
    expect(added?.wdkStepId).toBe(555);
  });

  it("inserts a combine step that references existing inputs", async () => {
    const strategy = makeStrategy([
      step({ id: "s1", displayName: "S1", searchName: "geneById", recordType: "gene" }),
      step({ id: "s2", displayName: "S2", searchName: "geneById", recordType: "gene" }),
    ]);
    const harness = makeQueryHarness(strategy);

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

    const { result } = renderHook(
      () => useAddStepMutation(strategy.id),
      { wrapper: harness.wrapper },
    );

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

    const c = harness.getStrategy(strategy.id)?.steps.find((s) => s.id === "c1");
    expect(c?.operator).toBe("INTERSECT");
    expect(c?.primaryInputStepId).toBe("s1");
    expect(c?.secondaryInputStepId).toBe("s2");
  });
});
