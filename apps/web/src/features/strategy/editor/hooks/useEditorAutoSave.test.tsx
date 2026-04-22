/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useEditorAutoSave } from "./useEditorAutoSave";

type Payload = { stepId: string; parameters: { a: string } };

interface MockMutation {
  mutate: ReturnType<typeof vi.fn<(payload: Payload) => void>>;
  mutateAsync: ReturnType<typeof vi.fn>;
  isPending: boolean;
}

function makeMutation(opts?: { isPending?: boolean }): MockMutation {
  return {
    mutate: vi.fn<(payload: Payload) => void>(),
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: opts?.isPending ?? false,
  };
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useEditorAutoSave", () => {
  it("debounces onChange triggers and submits once after 500ms", () => {
    const mutation = makeMutation();
    const { result } = renderHook(() =>
      useEditorAutoSave({
        debounceMs: 500,
        mutation: { mutate: mutation.mutate, isPending: mutation.isPending },
        getPayload: () => ({ stepId: "s1", parameters: { a: "b" } }),
      }),
    );
    act(() => {
      result.current.scheduleSave();
      result.current.scheduleSave();
      result.current.scheduleSave();
    });
    expect(mutation.mutate).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(499);
    });
    expect(mutation.mutate).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(2);
    });
    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      stepId: "s1",
      parameters: { a: "b" },
    });
  });

  it("submitNow cancels pending debounce and submits immediately", () => {
    const mutation = makeMutation();
    const { result } = renderHook(() =>
      useEditorAutoSave({
        debounceMs: 500,
        mutation: { mutate: mutation.mutate, isPending: mutation.isPending },
        getPayload: () => ({ stepId: "s1", parameters: { a: "b" } }),
      }),
    );
    act(() => {
      result.current.scheduleSave();
      result.current.submitNow();
    });
    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(mutation.mutate).toHaveBeenCalledTimes(1);
  });

  it("queues when mutation is pending and collapses queued triggers to one", () => {
    const mutation = makeMutation({ isPending: true });
    const { result, rerender } = renderHook(
      ({ pending }: { pending: boolean }) =>
        useEditorAutoSave({
          debounceMs: 500,
          mutation: { mutate: mutation.mutate, isPending: pending },
          getPayload: () => ({ stepId: "s1", parameters: { a: "b" } }),
        }),
      { initialProps: { pending: true } },
    );

    act(() => {
      result.current.submitNow();
      result.current.submitNow();
      result.current.submitNow();
    });
    expect(mutation.mutate).not.toHaveBeenCalled();

    rerender({ pending: false });

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
  });

  it("does not call mutate when getPayload returns null", () => {
    const mutation = makeMutation();
    const { result } = renderHook(() =>
      useEditorAutoSave({
        debounceMs: 500,
        mutation: { mutate: mutation.mutate, isPending: mutation.isPending },
        getPayload: () => null,
      }),
    );
    act(() => {
      result.current.submitNow();
    });
    expect(mutation.mutate).not.toHaveBeenCalled();
  });
});
