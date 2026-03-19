"use client";

import { useEffect } from "react";
import { useSessionStore } from "@/state/useSessionStore";
import { refreshAuth } from "@/lib/api/veupathdb-auth";

/**
 * Refreshes VEuPathDB auth cookies once per session after sign-in is detected.
 * Call from any page that requires an authenticated VEuPathDB session.
 */
export function useAuthRefresh(): void {
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const authRefreshed = useSessionStore((s) => s.authRefreshed);
  const setAuthRefreshed = useSessionStore((s) => s.setAuthRefreshed);
  const bumpAuthVersion = useSessionStore((s) => s.bumpAuthVersion);
  const selectedSite = useSessionStore((s) => s.selectedSite);

  useEffect(() => {
    if (!veupathdbSignedIn || authRefreshed) return;
    setAuthRefreshed(true);
    refreshAuth(selectedSite)
      .then(() => bumpAuthVersion())
      .catch((err) => {
        console.error("[refreshAuth]", err);
      });
  }, [
    veupathdbSignedIn,
    authRefreshed,
    setAuthRefreshed,
    bumpAuthVersion,
    selectedSite,
  ]);
}
