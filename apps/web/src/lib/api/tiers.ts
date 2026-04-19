import { queryOptions } from "@tanstack/react-query";
import { tierListResponseSchema } from "@pathfinder/shared/generated/zod/tierListResponseSchema";
import type { TierListResponse } from "@pathfinder/shared/generated/types/TierListResponse";

import { requestJson } from "./http";

export async function listTiers(): Promise<TierListResponse> {
  return await requestJson(tierListResponseSchema, "/api/v1/tiers");
}

export function tierPresetsOptions() {
  return queryOptions({
    queryKey: ["tiers"],
    queryFn: listTiers,
    staleTime: Infinity,
  });
}
