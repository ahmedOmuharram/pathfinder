import { queryOptions } from "@tanstack/react-query";

import type { QuotaResponse } from "@pathfinder/shared/generated/types/QuotaResponse";

import { client } from "./client";

export const userQuotaQueryKey = ["me", "quota"] as const;

async function getUserQuota(): Promise<QuotaResponse> {
  const res = await client<QuotaResponse>({
    method: "get",
    url: "/api/v1/me/quota",
  });
  return res.data;
}

export function userQuotaOptions() {
  return queryOptions({
    queryKey: userQuotaQueryKey,
    queryFn: getUserQuota,
    staleTime: 30_000,
  });
}
