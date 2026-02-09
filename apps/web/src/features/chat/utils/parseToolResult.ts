import { isRecord } from "@/shared/utils/isRecord";

export function parseToolResult(
  result?: string | null,
): { graphSnapshot?: Record<string, unknown> } | null {
  if (!result) return null;
  try {
    const parsed = JSON.parse(result);
    if (!isRecord(parsed)) return null;
    const graphSnapshot = parsed.graphSnapshot;
    if (graphSnapshot && isRecord(graphSnapshot)) {
      return { graphSnapshot };
    }
    return { graphSnapshot: undefined };
  } catch {
    return null;
  }
}
