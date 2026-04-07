import { queryOptions } from "@tanstack/react-query";
import { requestJson } from "./http";
import {
  SystemConfigResponseSchema,
  type SystemConfigResponse,
} from "./schemas/health";

export async function getSystemConfig(): Promise<SystemConfigResponse> {
  return await requestJson(SystemConfigResponseSchema, "/health/config");
}

export function systemConfigOptions() {
  return queryOptions({
    queryKey: ["config", "system"] as const,
    queryFn: getSystemConfig,
    staleTime: Infinity,
  });
}
