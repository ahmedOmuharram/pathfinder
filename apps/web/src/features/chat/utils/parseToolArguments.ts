import { isRecord } from "@/shared/utils/isRecord";

export function parseToolArguments(args: unknown): Record<string, unknown> {
  if (!args) return {};
  if (isRecord(args)) return args;
  if (typeof args !== "string") return {};
  try {
    const parsed = JSON.parse(args);
    if (isRecord(parsed)) return parsed;
    return {};
  } catch {
    return {};
  }
}
