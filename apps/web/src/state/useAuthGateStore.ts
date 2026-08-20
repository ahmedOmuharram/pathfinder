/**
 * The VEuPathDB sign-in gate. Every WDK-backed feature needs a registered
 * VEuPathDB login, so this store carries the open sign-in prompt and the
 * reason the server gave for it.
 */

import { toast } from "sonner";

import { wdkLoginRequiredDetail } from "@/lib/api/errors";
import { createStore } from "./middleware";

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

/**
 * Route a refusal that names a missing VEuPathDB login to the sign-in prompt.
 * Returns false for every other error, which stays with its own handler.
 */
export function handleWdkLoginRequired(err: unknown): boolean {
  const detail = wdkLoginRequiredDetail(err);
  if (detail === null) return false;
  toast.error(detail, { id: WDK_LOGIN_REQUIRED_TOAST_ID });
  useAuthGateStore.getState().requestSignIn(detail);
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
