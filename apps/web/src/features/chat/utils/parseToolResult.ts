import { isRecord } from "@/lib/utils/isRecord";
import type { GraphSnapshotInput } from "@/features/chat/utils/graphSnapshot";

export type ToolResultPayload = {
  graphSnapshot?: GraphSnapshotInput;
};

export function parseToolResult(result?: string | null): ToolResultPayload | null {
  if (!result) return null;
  try {
    const parsed = JSON.parse(result);
    if (!isRecord(parsed)) return null;
    const graphSnapshot = parsed["graphSnapshot"];
    if (graphSnapshot != null && isRecord(graphSnapshot)) {
      return { graphSnapshot: graphSnapshot as GraphSnapshotInput };
    }
    return {};
  } catch {
    return null;
  }
}
