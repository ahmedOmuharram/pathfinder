/**
 * @vitest-environment jsdom
 */

import type * as ConversationsModule from "@/lib/api/conversations";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";

const pushConversationMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/conversations", async (importOriginal) => {
  const actual =
    await importOriginal<typeof ConversationsModule>();
  return { ...actual, pushConversation: pushConversationMock };
});

const toastErrorMock = vi.hoisted(() => vi.fn());
const toastWarningMock = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: { error: toastErrorMock, warning: toastWarningMock, success: vi.fn() },
}));

import { useStrategyStore } from "@/state/strategy/store";
import { useUpdateStepMutation } from "./useUpdateStepMutation";
import { makeQueryHarness } from "./__tests__/strategyTestUtils";

function makeStrategy(): Strategy {
  return {
    id: "strategy-1",
    name: "Test",
    siteId: "plasmodb",
    recordType: "gene",
    steps: [
      {
        id: "s1",
        displayName: "Genes by taxon",
        searchName: "GenesByTaxon",
        recordType: "gene",
        parameters: { organism: "Plasmodium" },
        isBuilt: false,
        isFiltered: false,
      },
    ],
    rootStepId: "s1",
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
  toastWarningMock.mockReset();
});

describe("useUpdateStepMutation", () => {
  it("patches step.parameters in cache on mutate (optimistic)", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);
    pushConversationMock.mockResolvedValueOnce(initial);

    const { result } = renderHook(
      () => useUpdateStepMutation(initial.id),
      { wrapper: harness.wrapper },
    );

    let promise: Promise<unknown> | undefined;
    act(() => {
      promise = result.current.mutateAsync({
        stepId: "s1",
        patch: { parameters: { organism: "Toxoplasma" } },
      });
    });

    expect(
      harness.getStrategy(initial.id)?.steps[0]?.parameters?.["organism"],
    ).toBe("Toxoplasma");

    await act(async () => {
      await promise;
    });
  });

  it("rolls back on error", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);

    pushConversationMock.mockRejectedValueOnce(new Error("Boom"));
    const { result } = renderHook(
      () => useUpdateStepMutation(initial.id),
      { wrapper: harness.wrapper },
    );

    await act(async () => {
      await expect(
        result.current.mutateAsync({
          stepId: "s1",
          patch: { displayName: "Renamed locally" },
        }),
      ).rejects.toThrow("Boom");
    });

    await waitFor(() => {
      expect(harness.getStrategy(initial.id)?.steps[0]?.displayName).toBe(
        "Genes by taxon",
      );
    });
    expect(toastErrorMock).toHaveBeenCalled();
  });

  it("guards against duplicate concurrent updates with isPending", async () => {
    const initial = makeStrategy();
    const harness = makeQueryHarness(initial);
    let resolveFn!: (s: Strategy) => void;
    pushConversationMock.mockReturnValueOnce(
      new Promise<Strategy>((resolve) => {
        resolveFn = resolve;
      }),
    );

    const { result } = renderHook(
      () => useUpdateStepMutation(initial.id),
      { wrapper: harness.wrapper },
    );

    let p1: Promise<unknown> | undefined;
    act(() => {
      p1 = result.current.mutateAsync({
        stepId: "s1",
        patch: { displayName: "A" },
      });
    });
    await waitFor(() => expect(result.current.isPending).toBe(true));

    await act(async () => {
      resolveFn(initial);
      await p1;
    });
    expect(pushConversationMock).toHaveBeenCalledTimes(1);
  });
});
