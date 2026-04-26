/**
 * @vitest-environment jsdom
 */

import type * as ConversationsModule from "@/lib/api/conversations";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Step, Strategy } from "@pathfinder/shared";

const patchConversationStepMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual = await importOriginal<typeof ConversationsModule>();
  return { ...actual, patchConversationStep: patchConversationStepMock };
});

const toastErrorMock = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: { error: toastErrorMock, warning: vi.fn(), success: vi.fn() },
}));

vi.mock("@/state/useSessionStore", () => ({
  useSessionStore: <T,>(selector: (state: { selectedSite: string }) => T): T =>
    selector({ selectedSite: "plasmodb" }),
}));

import { useUpdateStepMutation } from "./useUpdateStepMutation";
import { makeQueryHarness } from "./__tests__/strategyTestUtils";

function makeStep(id: string, overrides: Partial<Step> = {}): Step {
  return {
    id,
    displayName: `Step ${id}`,
    searchName: "GenesByTaxon",
    recordType: "transcript",
    parameters: { organism: "Plasmodium" },
    isBuilt: false,
    isFiltered: false,
    ...overrides,
  };
}

function makeStrategy(steps: Step[]): Strategy {
  return {
    id: "strategy-1",
    name: "Test",
    siteId: "plasmodb",
    recordType: "transcript",
    steps,
    rootStepId: steps[0]?.id ?? null,
    isSaved: false,
    description: null,
    wdkStrategyId: null,
    wdkUrl: null,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  };
}

beforeEach(() => {
  patchConversationStepMock.mockReset();
  toastErrorMock.mockReset();
});

describe("useUpdateStepMutation", () => {
  it("writes only the returned step to cache, leaving sibling steps untouched", async () => {
    const stepA = makeStep("A", { parameters: { organism: "Pf3D7" } });
    const stepB = makeStep("B", { parameters: { organism: "PvP01" } });
    const stepC = makeStep("C", { parameters: { organism: "Pk" } });
    const initial = makeStrategy([stepA, stepB, stepC]);
    const harness = makeQueryHarness(initial);

    const updatedA: Step = {
      ...stepA,
      parameters: { organism: "Pf3D7,PvP01" },
      operator: "INTERSECT",
    };
    patchConversationStepMock.mockResolvedValueOnce(updatedA);

    const { result } = renderHook(
      () => useUpdateStepMutation(initial.id),
      { wrapper: harness.wrapper },
    );

    await act(async () => {
      await result.current.mutateAsync({
        stepId: "A",
        patch: { parameters: { organism: "Pf3D7,PvP01" }, operator: "INTERSECT" },
      });
    });

    const next = harness.getStrategy(initial.id);
    expect(next?.steps[0]).toEqual(updatedA);
    expect(next?.steps[1]).toEqual(stepB);
    expect(next?.steps[2]).toEqual(stepC);
    expect(patchConversationStepMock).toHaveBeenCalledTimes(1);
    expect(patchConversationStepMock).toHaveBeenCalledWith(
      initial.id,
      "A",
      { parameters: { organism: "Pf3D7,PvP01" }, operator: "INTERSECT" },
      "plasmodb",
    );
  });

  it("runs concurrent step patches in parallel and updates cache for both with no clobber", async () => {
    const stepA = makeStep("A", { parameters: { organism: "Pf3D7" } });
    const stepB = makeStep("B", { parameters: { organism: "PvP01" } });
    const stepC = makeStep("C", { parameters: { organism: "Pk" } });
    const initial = makeStrategy([stepA, stepB, stepC]);
    const harness = makeQueryHarness(initial);

    const PATCH_DELAY_MS = 100;
    const updatedA: Step = { ...stepA, parameters: { organism: "Pf3D7-NEW" } };
    const updatedB: Step = { ...stepB, parameters: { organism: "PvP01-NEW" } };

    patchConversationStepMock.mockImplementation(
      (_convId: string, stepId: string) =>
        new Promise<Step>((resolve) => {
          setTimeout(() => {
            resolve(stepId === "A" ? updatedA : updatedB);
          }, PATCH_DELAY_MS);
        }),
    );

    const { result } = renderHook(
      () => useUpdateStepMutation(initial.id),
      { wrapper: harness.wrapper },
    );

    const start = Date.now();
    await act(async () => {
      await Promise.all([
        result.current.mutateAsync({
          stepId: "A",
          patch: { parameters: { organism: "Pf3D7-NEW" } },
        }),
        result.current.mutateAsync({
          stepId: "B",
          patch: { parameters: { organism: "PvP01-NEW" } },
        }),
      ]);
    });
    const elapsed = Date.now() - start;

    expect(elapsed).toBeLessThan(PATCH_DELAY_MS * 2);
    expect(patchConversationStepMock).toHaveBeenCalledTimes(2);
    const next = harness.getStrategy(initial.id);
    expect(next?.steps[0]).toEqual(updatedA);
    expect(next?.steps[1]).toEqual(updatedB);
    expect(next?.steps[2]).toEqual(stepC);
  });

  it("rolls back to snapshot on error", async () => {
    const stepA = makeStep("A");
    const initial = makeStrategy([stepA]);
    const harness = makeQueryHarness(initial);

    patchConversationStepMock.mockRejectedValueOnce(new Error("Boom"));

    const { result } = renderHook(
      () => useUpdateStepMutation(initial.id),
      { wrapper: harness.wrapper },
    );

    await act(async () => {
      await expect(
        result.current.mutateAsync({
          stepId: "A",
          patch: { displayName: "Renamed locally" },
        }),
      ).rejects.toThrow("Boom");
    });

    await waitFor(() => {
      expect(harness.getStrategy(initial.id)?.steps[0]).toEqual(stepA);
    });
    expect(toastErrorMock).toHaveBeenCalled();
  });
});
