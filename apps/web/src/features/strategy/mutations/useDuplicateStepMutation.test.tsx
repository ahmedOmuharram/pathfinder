/**
 * @vitest-environment jsdom
 */

import type * as ConversationsModule from "@/lib/api/conversations";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Strategy, Step } from "@pathfinder/shared";

const pushConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual =
    await importOriginal<typeof ConversationsModule>();
  return { ...actual, pushConversation: pushConversationMock };
});

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
    const harness = makeQueryHarness(strategy);

    pushConversationMock.mockImplementationOnce(async (_id, args) => {
      return {
        ...strategy,
        steps: harness.getStrategy(strategy.id)?.steps ?? [],
        rootStepId: args.strategyAst.root.id,
      };
    });

    const { result } = renderHook(
      () => useDuplicateStepMutation(strategy.id),
      { wrapper: harness.wrapper },
    );

    let p: Promise<unknown> | undefined;
    act(() => {
      p = result.current.mutateAsync({ stepId: "s1" });
    });

    const optimisticSteps = harness.getStrategy(strategy.id)?.steps ?? [];
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
    const harness = makeQueryHarness(strategy);
    pushConversationMock.mockRejectedValueOnce(new Error("boom"));

    const { result } = renderHook(
      () => useDuplicateStepMutation(strategy.id),
      { wrapper: harness.wrapper },
    );

    await act(async () => {
      await expect(
        result.current.mutateAsync({ stepId: "s1" }),
      ).rejects.toThrow("boom");
    });

    await waitFor(() => {
      const steps = harness.getStrategy(strategy.id)?.steps ?? [];
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
    const harness = makeQueryHarness(strategy);

    pushConversationMock.mockImplementationOnce(async () => ({
      ...strategy,
      steps: harness.getStrategy(strategy.id)?.steps ?? [],
    }));

    const { result } = renderHook(
      () => useDuplicateStepMutation(strategy.id),
      { wrapper: harness.wrapper },
    );

    let p: Promise<unknown> | undefined;
    act(() => {
      p = result.current.mutateAsync({ stepId: "s1" });
    });

    const steps = harness.getStrategy(strategy.id)?.steps ?? [];
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
