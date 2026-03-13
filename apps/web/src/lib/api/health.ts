import { requestJsonValidated } from "./http";
import {
  SystemConfigResponseSchema,
  type SystemConfigResponse,
} from "./schemas/health";

export async function getSystemConfig(): Promise<SystemConfigResponse> {
  return await requestJsonValidated(SystemConfigResponseSchema, "/health/config");
}
