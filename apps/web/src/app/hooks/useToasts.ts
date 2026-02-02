import { useCallback, useRef, useState } from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
}

const DEFAULT_DURATION_MS = 3000;

export function useToasts(durationMs: number = DEFAULT_DURATION_MS) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef(new Map<string, number>());

  const removeToast = useCallback((id: string) => {
    const timerId = timers.current.get(id);
    if (timerId) {
      window.clearTimeout(timerId);
      timers.current.delete(id);
    }
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const addToast = useCallback(
    (toast: Omit<ToastItem, "id">) => {
      const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      setToasts((prev) => [...prev, { id, ...toast }]);
      const timerId = window.setTimeout(() => {
        removeToast(id);
      }, durationMs);
      timers.current.set(id, timerId);
    },
    [durationMs, removeToast]
  );

  return {
    toasts,
    addToast,
    removeToast,
    durationMs,
  };
}
