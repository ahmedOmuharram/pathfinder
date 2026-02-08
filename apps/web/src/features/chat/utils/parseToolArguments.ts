export function parseToolArguments(args: unknown): Record<string, unknown> {
  if (!args) return {};
  if (typeof args === "object" && args !== null && !Array.isArray(args)) {
    return args as Record<string, unknown>;
  }
  if (typeof args !== "string") return {};
  try {
    const parsed = JSON.parse(args);
    if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return {};
  } catch {
    return {};
  }
}
