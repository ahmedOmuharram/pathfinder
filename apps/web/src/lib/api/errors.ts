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
