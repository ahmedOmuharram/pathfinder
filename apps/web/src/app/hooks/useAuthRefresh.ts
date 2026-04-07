"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSessionStore } from "@/state/useSessionStore";
import { refreshAuth } from "@/lib/api/veupathdb-auth";
import { invalidateUserScopedQueries } from "@/lib/query/invalidateUserScoped";

/**
 * Refreshes VEuPathDB auth cookies once per session after sign-in is detected.
 * Call from any page that requires an authenticated VEuPathDB session.
 *
 * After a successful refresh, invalidates all user-scoped TQ caches so that
 * queries which previously failed due to stale cookies are retried.
 */
export function useAuthRefresh(): void {
  const queryClient = useQueryClient();
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const authRefreshed = useSessionStore((s) => s.authRefreshed);
  const setAuthRefreshed = useSessionStore((s) => s.setAuthRefreshed);
  const bumpAuthVersion = useSessionStore((s) => s.bumpAuthVersion);
  const selectedSite = useSessionStore((s) => s.selectedSite);

  useEffect(() => {
    if (!veupathdbSignedIn || authRefreshed) return;
    setAuthRefreshed(true);
    refreshAuth(selectedSite)
      .then(() => {
        bumpAuthVersion();
        invalidateUserScopedQueries(queryClient);
      })
      .catch((err) => {
        console.error("[refreshAuth]", err);
      });
  }, [
    veupathdbSignedIn,
    authRefreshed,
    setAuthRefreshed,
    bumpAuthVersion,
    selectedSite,
    queryClient,
  ]);
}
