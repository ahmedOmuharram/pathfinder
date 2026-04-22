import type { PipelineConfigPayload } from "@pathfinder/shared/generated/types/PipelineConfigPayload";
import type { UserPreferencesPatch } from "@pathfinder/shared/generated/types/UserPreferencesPatch";
import type { UserPreferencesResponse } from "@pathfinder/shared/generated/types/UserPreferencesResponse";
import {
  queryOptions,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";

import { client } from "./client";

export const userPreferencesQueryKey = ["me", "preferences"] as const;

export const DEFAULT_PIPELINE_CONFIG: PipelineConfigPayload = {
  provider: "openai",
  tier: "fast",
  phases: {
    scoping: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
    discovery: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
    planning: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
    execution: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
    verification: { modelId: "openai:gpt-4.1-mini", reasoningEffort: "medium" },
  },
};

async function getUserPreferences(): Promise<UserPreferencesResponse> {
  const res = await client<UserPreferencesResponse>({
    method: "get",
    url: "/api/v1/me/preferences",
  });
  return res.data;
}

export function userPreferencesOptions() {
  return queryOptions({
    queryKey: userPreferencesQueryKey,
    queryFn: getUserPreferences,
    staleTime: 60_000,
  });
}

export async function patchUserPreferences(
  patch: UserPreferencesPatch,
): Promise<UserPreferencesResponse> {
  const res = await client<UserPreferencesResponse>({
    method: "patch",
    url: "/api/v1/me/preferences",
    data: patch,
  });
  return res.data;
}

/**
 * Mutation hook for updating user preferences.
 *
 * Scoped to serialize rapid sequential PATCHes against the same user row —
 * TanStack queues mutations sharing a scope id so a tier-preset change
 * followed immediately by a per-phase effort bump don't race.
 *
 * On success the server returns the canonical payload; we seed the cache
 * directly so every ``useQuery(userPreferencesOptions())`` observer
 * re-renders in one round trip.
 */
export function useUpdateUserPreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchUserPreferences,
    scope: { id: "me-preferences" },
    onSuccess: (fresh) => {
      queryClient.setQueryData(userPreferencesQueryKey, fresh);
    },
  });
}
