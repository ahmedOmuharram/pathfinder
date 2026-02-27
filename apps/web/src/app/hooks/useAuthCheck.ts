"use client";

import { useEffect } from "react";
import { getVeupathdbAuthStatus } from "@/lib/api/client";
import { useSessionStore } from "@/state/useSessionStore";

/**
 * Runs initial VEuPathDB auth status check on mount.
 *
 * Authentication always runs against the VEuPathDB portal, regardless of
 * which component site is selected.
 *
 * :returns: Whether the initial auth check is still in progress.
 */
export function useAuthCheck(): { authLoading: boolean } {
  const authStatusKnown = useSessionStore((s) => s.authStatusKnown);
  const setVeupathdbAuth = useSessionStore((s) => s.setVeupathdbAuth);
  const setAuthStatusKnown = useSessionStore((s) => s.setAuthStatusKnown);

  useEffect(() => {
    if (authStatusKnown) return;
    let cancelled = false;
    getVeupathdbAuthStatus()
      .then((status) => {
        if (!cancelled) {
          setVeupathdbAuth(status.signedIn, status.name ?? null);
          setAuthStatusKnown(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setVeupathdbAuth(false, null);
          setAuthStatusKnown(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [authStatusKnown, setVeupathdbAuth, setAuthStatusKnown]);

  return { authLoading: !authStatusKnown };
}
