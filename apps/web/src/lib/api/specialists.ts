import type { SpecialistKind } from "@pathfinder/shared";
import type { SpecialistEnterResponse } from "@pathfinder/shared/generated/types/SpecialistEnterResponse";
import type { SpecialistExitResponse } from "@pathfinder/shared/generated/types/SpecialistExitResponse";
import type { SpecialistStateResponse } from "@pathfinder/shared/generated/types/SpecialistStateResponse";
import { specialistEnterResponseSchema } from "@pathfinder/shared/generated/zod/specialistEnterResponseSchema";
import { specialistExitResponseSchema } from "@pathfinder/shared/generated/zod/specialistExitResponseSchema";
import { specialistStateResponseSchema } from "@pathfinder/shared/generated/zod/specialistStateResponseSchema";

import { APIError, requestJson } from "./http";

export type {
  SpecialistEnterResponse,
  SpecialistExitResponse,
  SpecialistStateResponse,
};

export class SpecialistEnterRefusedError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "SpecialistEnterRefusedError";
    this.status = status;
  }
}

export async function enterSpecialist(args: {
  conversationId: string;
  kind: SpecialistKind;
  arg?: string;
  modelId?: string;
}): Promise<SpecialistEnterResponse> {
  const { conversationId, kind, arg = "", modelId } = args;
  const body: { arg: string; modelId?: string } = { arg };
  if (modelId !== undefined) body.modelId = modelId;
  try {
    return await requestJson(
      specialistEnterResponseSchema,
      `/api/v1/conversations/${conversationId}/specialists/${kind}/enter`,
      { method: "POST", body },
    );
  } catch (err) {
    if (err instanceof APIError && err.status === 409) {
      throw new SpecialistEnterRefusedError(err.status, err.message);
    }
    throw err;
  }
}

export async function exitSpecialist(
  conversationId: string,
): Promise<SpecialistExitResponse> {
  return await requestJson(
    specialistExitResponseSchema,
    `/api/v1/conversations/${conversationId}/specialists/exit`,
    { method: "POST", body: {} },
  );
}

export async function patchSpecialistModel(args: {
  conversationId: string;
  modelId: string;
}): Promise<SpecialistStateResponse> {
  return await requestJson(
    specialistStateResponseSchema,
    `/api/v1/conversations/${args.conversationId}/specialists/state`,
    { method: "PATCH", body: { modelId: args.modelId } },
  );
}
