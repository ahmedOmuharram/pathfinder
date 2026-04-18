"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSessionStore } from "@/state/useSessionStore";
import {
  authRefreshOptions,
  authStatusOptions,
  refreshAuth,
} from "@/lib/api/veupathdb-auth";
import { invalidateUserScopedQueries } from "@/lib/query/invalidateUserScoped";

/**
 * One-shot internal-token refresh keyed by site. Returns whether the refresh
 * has settled (success or failure) so consumers can gate dependent queries.
 * Running this hook from multiple components is safe — TanStack Query
 * deduplicates by queryKey.
 */
export function useAuthRefresh(): { authRefreshed: boolean } {
  const queryClient = useQueryClient();
  const selectedSite = useSessionStore((s) => s.selectedSite);

  const statusQuery = useQuery(authStatusOptions(selectedSite));
  const signedIn = statusQuery.data?.signedIn === true;

  const base = authRefreshOptions(selectedSite);
  const refreshQuery = useQuery({
    ...base,
    queryFn: async () => {
      await refreshAuth(selectedSite);
      invalidateUserScopedQueries(queryClient);
      return { refreshed: true };
    },
    enabled: signedIn,
  });

  return {
    authRefreshed: refreshQuery.isSuccess || refreshQuery.isError,
  };
}
