"use client";

import { useState } from "react";
import { getVeupathdbAuthStatus, loginVeupathdb } from "@/lib/api/client";
import { useSessionStore } from "@/state/useSessionStore";

interface SignInFormProps {
  /** Called when sign-in succeeds. */
  onSuccess?: () => void;
}

/**
 * VEuPathDB sign-in form (email + password).
 *
 * Always authenticates against the VEuPathDB portal.
 */
export function SignInForm({ onSuccess }: SignInFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);

  const setVeupathdbAuth = useSessionStore((state) => state.setVeupathdbAuth);
  const setAuthToken = useSessionStore((state) => state.setAuthToken);

  const handleSubmit = async () => {
    setAuthError(null);
    setAuthBusy(true);
    try {
      const result = await loginVeupathdb(email, password);
      if (result.authToken) {
        setAuthToken(result.authToken);
      }
      const status = await getVeupathdbAuthStatus();
      setVeupathdbAuth(status.signedIn, status.name ?? null);
      if (status.signedIn) {
        onSuccess?.();
      } else {
        setAuthError("Login failed. Please check your credentials.");
      }
    } catch {
      setAuthError("Login failed. Please try again.");
    } finally {
      setAuthBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="space-y-2.5">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !authBusy) void handleSubmit();
          }}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
        />
      </div>
      {authError && (
        <div className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {authError}
        </div>
      )}
      <button
        type="button"
        disabled={authBusy}
        onClick={handleSubmit}
        className="w-full rounded-md bg-primary px-3 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition-all duration-150 hover:bg-primary/90 hover:-translate-y-px active:translate-y-0 disabled:opacity-60"
      >
        {authBusy ? "Signing in..." : "Sign in"}
      </button>
      <p className="text-center text-[11px] text-muted-foreground">
        We do not store your login credentials.
      </p>
    </div>
  );
}
