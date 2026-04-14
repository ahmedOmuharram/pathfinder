import { create } from "zustand";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
}

const DEFAULT_DURATION_MS = 3000;

interface ToastStore {
  toasts: ToastItem[];
  durationMs: number;
  timers: Map<string, number>;
  addToast: (toast: Omit<ToastItem, "id">) => void;
  removeToast: (id: string) => void;
}

const useToastStore = create<ToastStore>((set, get) => ({
  toasts: [],
  durationMs: DEFAULT_DURATION_MS,
  timers: new Map(),
  removeToast: (id) => {
    const { timers } = get();
    const timerId = timers.get(id);
    if (timerId !== undefined) {
      window.clearTimeout(timerId);
      timers.delete(id);
    }
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
  addToast: (toast) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const { durationMs, timers, removeToast } = get();
    set((state) => ({ toasts: [...state.toasts, { id, ...toast }] }));
    const timerId = window.setTimeout(() => {
      removeToast(id);
    }, durationMs);
    timers.set(id, timerId);
  },
}));

export function useToasts(durationMs: number = DEFAULT_DURATION_MS) {
  const toasts = useToastStore((s) => s.toasts);
  const addToast = useToastStore((s) => s.addToast);
  const removeToast = useToastStore((s) => s.removeToast);
  useToastStore.setState({ durationMs });
  return { toasts, addToast, removeToast, durationMs };
}
