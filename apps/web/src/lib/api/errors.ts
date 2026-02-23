import { APIError } from "./http";
import { AppError } from "@/lib/errors/AppError";
import { isRecord } from "@/lib/utils/isRecord";

export type ProblemDetail = {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  code?: string;
  errors?: Array<Record<string, unknown>>;
};

export function isProblemDetail(value: unknown): value is ProblemDetail {
  if (!isRecord(value)) return false;
  const record = value;
  // Most FastAPI problem+json responses include these.
  return (
    typeof record.title === "string" &&
    typeof record.status === "number" &&
    typeof record.detail === "string"
  );
}

export function toUserMessage(err: unknown, fallback = "Request failed."): string {
  if (!err) return fallback;

  if (err instanceof AppError) {
    const msg = (err.message || "").trim();
    return msg || fallback;
  }

  if (err instanceof APIError) {
    const data = err.data;
    if (isProblemDetail(data)) {
      const msg = (data.detail || data.title || "").trim();
      return msg || fallback;
    }
    if (isRecord(data)) {
      const detail = data.detail;
      if (typeof detail === "string" && detail.trim()) return detail;
    }
    const msg = (err.message || "").trim();
    return msg || err.statusText || fallback;
  }

  if (err instanceof Error) {
    const msg = (err.message || "").trim();
    return msg || fallback;
  }

  try {
    const msg = String(err).trim();
    return msg || fallback;
  } catch {
    return fallback;
  }
}
