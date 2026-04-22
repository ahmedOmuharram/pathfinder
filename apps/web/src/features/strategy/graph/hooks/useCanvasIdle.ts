"use client";

import { useDebounceValue } from "usehooks-ts";
import { useStore } from "@xyflow/react";

interface UseCanvasIdleOptions {
  /** Idle threshold in milliseconds. */
  idleMs: number;
}

/**
 * Returns `true` when the canvas viewport (transform: x, y, zoom) has been
 * stable for at least `idleMs` milliseconds, otherwise `false`.
 *
 * Implementation: subscribes to the React Flow viewport transform via
 * `useStore`, then debounces a "version" counter through `useDebounceValue`.
 * The debounced version lags the live version while activity continues, so
 * "live === debounced" is the idle signal.
 */
export function useCanvasIdle({ idleMs }: UseCanvasIdleOptions): boolean {
  const transformSig = useStore((s) => {
    const t = s.transform;
    return `${t[0]}|${t[1]}|${t[2]}`;
  });
  const [debouncedSig] = useDebounceValue<string>(transformSig, idleMs);
  return transformSig === debouncedSig;
}
