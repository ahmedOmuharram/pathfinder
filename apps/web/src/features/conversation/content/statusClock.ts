import { useSyncExternalStore } from "react";

const SILENT_THRESHOLD_SECONDS = 10;

type Listener = () => void;

const listeners = new Set<Listener>();
let interval: ReturnType<typeof setInterval> | null = null;

export function currentSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

let nowSeconds = currentSeconds();

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  if (interval === null) {
    nowSeconds = currentSeconds();
    interval = setInterval(() => {
      nowSeconds = currentSeconds();
      for (const each of listeners) each();
    }, 1000);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && interval !== null) {
      clearInterval(interval);
      interval = null;
    }
  };
}

export function getNowSeconds(): number {
  return nowSeconds;
}

export function useNowSeconds(): number {
  return useSyncExternalStore(subscribe, getNowSeconds, getNowSeconds);
}

export function formatElapsed(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return minutes === 0 ? `${rest}s` : `${minutes}m ${rest}s`;
}

/** The elapsed time joins the label only after the turn goes quiet. */
export function statusLineWith(label: string, silentSeconds: number): string {
  if (silentSeconds < SILENT_THRESHOLD_SECONDS) return label;
  return `${label.replace(/\.+$/, "")}, ${formatElapsed(silentSeconds)}`;
}
