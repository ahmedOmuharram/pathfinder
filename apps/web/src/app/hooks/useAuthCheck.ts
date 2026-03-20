"use client";

import { useCallback, useEffect, useState } from "react";
import { getVeupathdbAuthStatus } from "@/lib/api/veupathdb-auth";
import { useSessionStore } from "@/state/useSessionStore";

/**
 * Runs initial VEuPathDB auth status check on mount.
 *
 * Returns loading state and an apiError string when the backend is
 * unreachable so the page can render a proper error screen.
 */
export function useAuthCheck(): {
  authLoading: boolean;
  apiError: string | null;
  retry: () => void;
} {
  const authStatusKnown = useSessionStore((s) => s.authStatusKnown);
  const setVeupathdbAuth = useSessionStore((s) => s.setVeupathdbAuth);
  const setAuthStatusKnown = useSessionStore((s) => s.setAuthStatusKnown);
  const selectedSite = useSessionStore((s) => s.selectedSite);
  const [apiError, setApiError] = useState<string | null>(null);

  const runCheck = useCallback(() => {
    setApiError(null);
    let cancelled = false;
    getVeupathdbAuthStatus(selectedSite)
      .then((status) => {
        if (!cancelled) {
          setVeupathdbAuth(status.signedIn, status.name ?? null);
          setAuthStatusKnown(true);
        }
      })
      .catch((err) => {
        console.error("[useAuthCheck]", err);
        if (!cancelled) {
          setApiError(err instanceof Error ? err.message : "Unable to reach the API.");
          setAuthStatusKnown(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSite, setVeupathdbAuth, setAuthStatusKnown]);

  useEffect(() => {
    if (authStatusKnown && apiError === null) return;
    let cleanup: (() => void) | undefined;
    const id = setTimeout(() => {
      cleanup = runCheck();
    }, 0);
    return () => {
      clearTimeout(id);
      cleanup?.();
    };
  }, [authStatusKnown, apiError, runCheck]);

  const retry = useCallback(() => {
    setApiError(null);
    setAuthStatusKnown(false);
  }, [setAuthStatusKnown]);

  return { authLoading: !authStatusKnown, apiError, retry };
}
