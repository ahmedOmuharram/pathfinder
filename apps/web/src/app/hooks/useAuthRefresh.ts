"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";
import { useSessionStore } from "@/state/useSessionStore";
import { refreshAuth } from "@/lib/api/veupathdb-auth";
import { invalidateUserScopedQueries } from "@/lib/query/invalidateUserScoped";

export function useAuthRefresh(): void {
  const queryClient = useQueryClient();
  const {
    veupathdbSignedIn,
    authRefreshed,
    setAuthRefreshed,
    bumpAuthVersion,
    selectedSite,
  } = useSessionStore(
    useShallow((s) => ({
      veupathdbSignedIn: s.veupathdbSignedIn,
      authRefreshed: s.authRefreshed,
      setAuthRefreshed: s.setAuthRefreshed,
      bumpAuthVersion: s.bumpAuthVersion,
      selectedSite: s.selectedSite,
    })),
  );

  useQuery({
    queryKey: ["auth", "refresh", selectedSite] as const,
    queryFn: async () => {
      setAuthRefreshed(true);
      await refreshAuth(selectedSite);
      bumpAuthVersion();
      invalidateUserScopedQueries(queryClient);
      return { refreshed: true };
    },
    enabled: veupathdbSignedIn && !authRefreshed,
    staleTime: Infinity,
    retry: false,
  });
}
