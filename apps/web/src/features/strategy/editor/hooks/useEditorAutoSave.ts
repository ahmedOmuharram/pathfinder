"use client";

import { useRef, useState } from "react";
import { useEventCallback } from "usehooks-ts";

interface AutoSaveMutationLike<TPayload> {
  mutate: (payload: TPayload) => void;
  isPending: boolean;
}

interface UseEditorAutoSaveArgs<TPayload> {
  /** Source of the latest payload to submit. Return `null` to skip the submit. */
  getPayload: () => TPayload | null;
  mutation: AutoSaveMutationLike<TPayload>;
  /** Debounce window for `scheduleSave`. Default 500ms. */
  debounceMs?: number;
}

interface AutoSave {
  /** Schedule a debounced save (collapses repeated triggers within the window). */
  scheduleSave: () => void;
  /** Cancel any pending debounce and submit immediately. */
  submitNow: () => void;
}

/**
 * Auto-save controller. `scheduleSave` debounces; `submitNow` flushes immediately.
 * If a mutation is in flight when a submit is requested, the next submit is
 * queued; further triggers in the queue collapse to one.
 *
 * Reconciliation of the in-flight queue is render-time (no useEffect): when
 * `mutation.isPending` transitions from true → false and `pendingQueued` is
 * true, we drain the queue.
 */
export function useEditorAutoSave<TPayload>(
  args: UseEditorAutoSaveArgs<TPayload>,
): AutoSave {
  const { getPayload, mutation, debounceMs = 500 } = args;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [queued, setQueued] = useState(false);
  const [prevPending, setPrevPending] = useState(mutation.isPending);

  const stableGetPayload = useEventCallback(getPayload);

  const submit = (): void => {
    const payload = stableGetPayload();
    if (payload === null) return;
    if (mutation.isPending) {
      setQueued(true);
      return;
    }
    mutation.mutate(payload);
  };

  // Render-time queue drain: when isPending flips false and a queue exists, fire one.
  if (mutation.isPending !== prevPending) {
    setPrevPending(mutation.isPending);
    if (!mutation.isPending && queued) {
      setQueued(false);
      const payload = stableGetPayload();
      if (payload !== null) {
        mutation.mutate(payload);
      }
    }
  }

  const scheduleSave = (): void => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      submit();
    }, debounceMs);
  };

  const submitNow = (): void => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    submit();
  };

  return { scheduleSave, submitNow };
}
