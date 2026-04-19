import { queryOptions } from "@tanstack/react-query";

import type { UserPreferencesPatch } from "@pathfinder/shared/generated/types/UserPreferencesPatch";
import type { UserPreferencesResponse } from "@pathfinder/shared/generated/types/UserPreferencesResponse";

import { client } from "./client";

export const userPreferencesQueryKey = ["me", "preferences"] as const;

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
