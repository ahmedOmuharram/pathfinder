import { requestJson } from "./http";
import {
  SystemConfigResponseSchema,
  type SystemConfigResponse,
} from "./schemas/health";

export async function getSystemConfig(): Promise<SystemConfigResponse> {
  return await requestJson(SystemConfigResponseSchema, "/health/config");
}
