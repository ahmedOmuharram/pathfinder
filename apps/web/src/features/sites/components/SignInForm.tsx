"use client";

import { useState } from "react";
import { getVeupathdbAuthStatus, loginVeupathdb } from "@/lib/api/veupathdb-auth";
import { useSessionStore } from "@/state/useSessionStore";
import { Input } from "@/lib/components/ui/Input";

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
  const selectedSite = useSessionStore((state) => state.selectedSite);

  const handleSubmit = async () => {
    setAuthError(null);
    setAuthBusy(true);
    try {
      await loginVeupathdb(email, password, selectedSite);
      const status = await getVeupathdbAuthStatus(selectedSite);
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
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
        />
        <Input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !authBusy) void handleSubmit();
          }}
        />
      </div>
      {authError != null && (
        <div className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {authError}
        </div>
      )}
      <button
        type="button"
        disabled={authBusy}
        onClick={() => {
          void handleSubmit();
        }}
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
