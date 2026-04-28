import type { OptimizeLaunchRequest } from "@pathfinder/shared/generated/types/OptimizeLaunchRequest";
import type { OptimizeLaunchResponse } from "@pathfinder/shared/generated/types/OptimizeLaunchResponse";
import { optimizeLaunchResponseSchema } from "@pathfinder/shared/generated/zod/optimizeLaunchResponseSchema";

import { APIError, requestJson } from "./http";

export type { OptimizeLaunchRequest, OptimizeLaunchResponse };

export class LauncherPreconditionError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "LauncherPreconditionError";
    this.status = status;
    this.detail = detail;
  }
}

export async function postOptimizeLaunch(
  conversationId: string,
  body: OptimizeLaunchRequest,
): Promise<OptimizeLaunchResponse> {
  try {
    return await requestJson(
      optimizeLaunchResponseSchema,
      `/api/v1/conversations/${conversationId}/launchers/optimize`,
      { method: "POST", body },
    );
  } catch (err) {
    if (err instanceof APIError && err.status === 409) {
      throw new LauncherPreconditionError(err.status, err.message);
    }
    throw err;
  }
}
