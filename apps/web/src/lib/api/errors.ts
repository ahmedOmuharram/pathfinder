import { z } from "zod";

import { APIError } from "./http";
import { AppError } from "@/lib/errors/AppError";
import { isRecord } from "@/lib/utils/isRecord";

/** FastAPI validation error item: `{loc: [...], msg: string, type: string}`. */
type ValidationErrorItem = {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
};

type ProblemDetail = {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  code?: string;
  errors?: ValidationErrorItem[];
};

export function isProblemDetail(value: unknown): value is ProblemDetail {
  if (!isRecord(value)) return false;
  const record = value;
  // Most FastAPI problem+json responses include these.
  return (
    typeof record["title"] === "string" &&
    typeof record["status"] === "number" &&
    typeof record["detail"] === "string"
  );
}

export function toUserMessage(err: unknown, fallback = "Request failed."): string {
  if (err == null) return fallback;

  if (err instanceof AppError) {
    const msg = err.message.trim();
    return msg !== "" ? msg : fallback;
  }

  if (err instanceof APIError) {
    const data = err.data;
    if (isProblemDetail(data)) {
      const msg = (data.detail ?? data.title ?? "").trim();
      return msg !== "" ? msg : fallback;
    }
    if (isRecord(data)) {
      const detail = data["detail"];
      if (typeof detail === "string" && detail.trim() !== "") return detail;
    }
    const msg = err.message.trim();
    return msg !== "" ? msg : err.statusText !== "" ? err.statusText : fallback;
  }

  if (err instanceof Error) {
    const msg = err.message.trim();
    return msg !== "" ? msg : fallback;
  }

  try {
    const msg = String(err).trim();
    return msg !== "" ? msg : fallback;
  } catch {
    return fallback;
  }
}

const wdkAuthRefusalSchema = z.object({
  code: z.union([z.literal("WDK_LOGIN_REQUIRED"), z.literal("WDK_IDENTITY_MISMATCH")]),
  detail: z.string().min(1),
});

/** A refusal about which VEuPathDB account the request acts as. */
export type WdkAuthRefusal = z.infer<typeof wdkAuthRefusalSchema>;

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/**
 * The server's refusal when a route wants a VEuPathDB login or reports that the
 * token names another account, or null for every other error. The chat
 * transport rethrows the response body as the message of a plain Error, so both
 * shapes are read here.
 */
export function wdkAuthRefusal(err: unknown): WdkAuthRefusal | null {
  if (!(err instanceof Error)) return null;
  if (err instanceof APIError && err.status !== 401) return null;
  const body = err instanceof APIError ? err.data : parseJson(err.message);
  const problem = wdkAuthRefusalSchema.safeParse(body);
  return problem.success ? problem.data : null;
}
