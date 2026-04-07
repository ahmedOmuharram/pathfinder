"use client";

import { useCallback, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authStatusOptions } from "@/lib/api/veupathdb-auth";
import { invalidateUserScopedQueries } from "@/lib/query/invalidateUserScoped";
import { useSessionStore } from "@/state/useSessionStore";

/**
 * Runs initial VEuPathDB auth status check on mount.
 *
 * Returns loading state and an apiError string when the backend is
 * unreachable so the page can render a proper error screen.
 *
 * Auth state is written to `useSessionStore` because it is consumed
 * globally across the app — many components read `veupathdbSignedIn`
 * without using this hook.
 */
export function useAuthCheck(): {
  authLoading: boolean;
  apiError: string | null;
  retry: () => void;
} {
  const queryClient = useQueryClient();
  const authStatusKnown = useSessionStore((s) => s.authStatusKnown);
  const setVeupathdbAuth = useSessionStore((s) => s.setVeupathdbAuth);
  const setAuthStatusKnown = useSessionStore((s) => s.setAuthStatusKnown);
  const selectedSite = useSessionStore((s) => s.selectedSite);

  const bumpAuthVersion = useSessionStore((s) => s.bumpAuthVersion);

  const authOpts = authStatusOptions(selectedSite);
  const { data, error, isPending } = useQuery(authOpts);

  // Track previous signed-in state so we only invalidate on actual transitions.
  const prevSignedInRef = useRef<boolean | null>(null);

  // Sync successful auth status to Zustand store.
  // When the signed-in state transitions (login or logout), invalidate all
  // user-scoped TQ caches so strategies, gene sets, etc. re-fetch.
  useEffect(() => {
    if (data === undefined) return;
    setVeupathdbAuth(data.signedIn, data.name ?? null);
    setAuthStatusKnown(true);

    const prev = prevSignedInRef.current;
    prevSignedInRef.current = data.signedIn;

    // Only invalidate when signed-in state actually changes, not on every
    // successful auth poll.  Skip the very first check (prev === null) since
    // there is no stale cache to clear on initial mount.
    if (prev !== null && prev !== data.signedIn) {
      invalidateUserScopedQueries(queryClient);
      bumpAuthVersion();
    }
  }, [data, setVeupathdbAuth, setAuthStatusKnown, queryClient, bumpAuthVersion]);

  // On error, still mark auth as known so the app can render the error screen.
  useEffect(() => {
    if (error === null) return;
    console.error("[useAuthCheck]", error);
    setAuthStatusKnown(true);
  }, [error, setAuthStatusKnown]);

  const apiError =
    error !== null
      ? error instanceof Error
        ? error.message
        : "Unable to reach the API."
      : null;

  const retry = useCallback(() => {
    void queryClient.invalidateQueries({
      queryKey: authOpts.queryKey,
    });
  }, [queryClient, authOpts.queryKey]);

  return { authLoading: !authStatusKnown && isPending, apiError, retry };
}
