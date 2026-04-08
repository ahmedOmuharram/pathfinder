import { queryOptions } from "@tanstack/react-query";
import { requestJson } from "./http";
import {
  TierListResponseSchema,
  type TierListResponse,
} from "./schemas/tiers";

export async function listTiers(): Promise<TierListResponse> {
  return await requestJson(
    TierListResponseSchema,
    "/api/v1/tiers",
  );
}

export function tierPresetsOptions() {
  return queryOptions({
    queryKey: ["tiers"],
    queryFn: listTiers,
    staleTime: Infinity,
  });
}
