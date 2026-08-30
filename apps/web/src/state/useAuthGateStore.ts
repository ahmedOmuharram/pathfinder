/**
 * The VEuPathDB sign-in gate. Every WDK-backed feature needs a registered
 * VEuPathDB login, so this store carries the open sign-in prompt and the
 * reason the server gave for it.
 */

import { toast } from "sonner";

import { wdkAuthRefusal } from "@/lib/api/errors";
import { refreshAuth } from "@/lib/api/veupathdb-auth";
import { createStore } from "./middleware";
import { useSessionStore } from "./useSessionStore";

interface AuthGateState {
  signInRequired: boolean;
  /** The server's explanation, or null when the user asked to sign in. */
  signInReason: string | null;

  requestSignIn: (reason?: string) => void;
  dismissSignIn: () => void;
}

export const useAuthGateStore = createStore<AuthGateState>("AuthGateStore", (set) => ({
  signInRequired: false,
  signInReason: null,

  requestSignIn: (reason) =>
    set((s) => {
      const next = reason ?? null;
      if (s.signInRequired && s.signInReason === next) return s;
      return { signInRequired: true, signInReason: next };
    }),

  dismissSignIn: () =>
    set((s) =>
      s.signInRequired || s.signInReason !== null
        ? { signInRequired: false, signInReason: null }
        : s,
    ),
}));

/** One toast for the whole gate, so concurrent refusals replace it. */
export const WDK_LOGIN_REQUIRED_TOAST_ID = "wdk-login-required";

function promptSignIn(detail: string): void {
  toast.error(detail, { id: WDK_LOGIN_REQUIRED_TOAST_ID });
  useAuthGateStore.getState().requestSignIn(detail);
}

/** The relink in flight, so a burst of refusals costs one refresh. */
let relinking: Promise<boolean> | null = null;

async function relink(detail: string, retry?: () => void): Promise<void> {
  relinking ??= refreshAuth(useSessionStore.getState().selectedSite)
    .then((result) => result.success)
    .catch(() => false);
  const relinked = await relinking;
  relinking = null;
  if (!relinked) {
    promptSignIn(detail);
    return;
  }
  retry?.();
}

/**
 * Route a refusal about the caller's VEuPathDB account. A missing login opens
 * the sign-in prompt. A token that names another account relinks the session
 * first, and calls ``retry`` when the relink succeeds. Returns false for every
 * other error, which stays with its own handler.
 */
export function handleWdkAuthRefusal(err: unknown, retry?: () => void): boolean {
  const refusal = wdkAuthRefusal(err);
  if (refusal === null) return false;
  if (refusal.code === "WDK_IDENTITY_MISMATCH") {
    void relink(refusal.detail, retry);
    return true;
  }
  promptSignIn(refusal.detail);
  return true;
}

/**
 * True when the session must be replaced by the sign-in prompt. An embedded
 * session renders instead, and its composer carries the prompt in place.
 */
export function requiresFullScreenSignIn({
  embedded,
  signedIn,
}: {
  embedded: boolean;
  signedIn: boolean;
}): boolean {
  return !signedIn && !embedded;
}
