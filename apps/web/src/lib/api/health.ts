import { queryOptions } from "@tanstack/react-query";
import { systemConfigResponseSchema } from "@pathfinder/shared/generated/zod/systemConfigResponseSchema";
import type { SystemConfigResponse } from "@pathfinder/shared/generated/types/SystemConfigResponse";

import { requestJson } from "./http";

export async function getSystemConfig(): Promise<SystemConfigResponse> {
  return await requestJson(systemConfigResponseSchema, "/health/config");
}

export function systemConfigOptions() {
  return queryOptions({
    queryKey: ["config", "system"] as const,
    queryFn: getSystemConfig,
    staleTime: Infinity,
  });
}
