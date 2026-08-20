"use client";

import { useQuery } from "@tanstack/react-query";
import { LogIn } from "lucide-react";

import { authStatusOptions } from "@/lib/api/veupathdb-auth";
import { useAuthGateStore } from "@/state/useAuthGateStore";
import { useSessionStore } from "@/state/useSessionStore";

export const SIGN_IN_TO_BUILD = "Sign in to VEuPathDB to build strategies";

/** True only when VEuPathDB reports a registered login for the current site. */
export function useVeupathdbSignedIn(): boolean {
  const siteId = useSessionStore((s) => s.selectedSite);
  const { data } = useQuery(authStatusOptions(siteId));
  return data?.signedIn === true;
}

export function VeupathdbSignInRequired() {
  const signedIn = useVeupathdbSignedIn();
  const requestSignIn = useAuthGateStore((s) => s.requestSignIn);
  if (signedIn) return null;

  return (
    <div
      role="alert"
      data-testid="veupathdb-signin-required"
      className="mx-auto flex w-full max-w-3xl items-center gap-3 border-t border-border bg-muted/40 px-4 py-2.5 text-sm"
    >
      <LogIn className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <p className="min-w-0 flex-1 text-muted-foreground">
        {SIGN_IN_TO_BUILD}. Searches, strategies and gene sets need a VEuPathDB account.
      </p>
      <button
        type="button"
        onClick={() => requestSignIn()}
        className="shrink-0 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-transform hover:-translate-y-px"
      >
        Sign in
      </button>
    </div>
  );
}
