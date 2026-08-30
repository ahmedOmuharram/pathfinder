/**
 * The guarded client import and the helpers over it.
 * Frozen with the buildTrace acceptance modules: implementers may not touch tests/acceptance/**.
 */
import type { ClientApi, TraceShape } from "./traceTypes";
import { TURN } from "./traceTurn";

/** The host's figure set. `data-turn-failed` and `data-turn-stopped` are
 * notices the message renders at turn level, so they are absent by design. */
export const RENDERING_KINDS: ReadonlySet<string> = new Set([
  "data-eda.analysis-state",
  "data-eda.subset-preview",
  "data-eda.viz",
  "data-strategy-link",
  "data-gene-set",
  "data-enrichment-results",
  "data-verification-summary",
  "data-variant-comparison",
  "data-scored-comparison",
  "data-graph-snapshot",
  "data-graph-cleared",
  "data-memory-retrieved",
]);

async function loadClient(): Promise<ClientApi | null> {
  try {
    const loaded: unknown = await import("../../../src/index.ts");
    const candidate = loaded as Partial<ClientApi>;
    const buildTrace = candidate.buildTrace;
    const reduceTurn = candidate.reduceTurn;
    if (typeof buildTrace !== "function") return null;
    if (typeof reduceTurn !== "function") return null;
    return { buildTrace, reduceTurn };
  } catch {
    return null;
  }
}

export const client = await loadClient();

export function api(): ClientApi {
  return client as ClientApi;
}

export function runs(parts: readonly unknown[]): TraceShape[] {
  return api().buildTrace(parts, { renderingKinds: RENDERING_KINDS });
}

export function at<T>(items: readonly T[], index: number): T {
  const item = items[index];
  if (item === undefined) throw new Error(`no item at index ${String(index)}`);
  return item;
}

/** The AI SDK path: the summary survives as its own data part beside the tool
 * part, because the SDK's reducer does not implement the reduction rule. */
export function sdkParts(): unknown[] {
  const parts = api().reduceTurn(
    TURN.filter((c) => c.type !== "data-tool-summary"),
  ).parts;
  for (const chunk of TURN) {
    if (chunk.type !== "data-tool-summary") continue;
    const data = chunk["data"] as { toolCallId: string };
    const index = parts.findIndex(
      (part) => (part as { toolCallId?: string }).toolCallId === data.toolCallId,
    );
    if (index < 0) throw new Error(`no tool part for ${data.toolCallId}`);
    parts.splice(index + 1, 0, { type: "data-tool-summary", data });
  }
  return parts;
}

export function tool(name: string, id: string): unknown {
  return {
    type: `tool-${name}`,
    toolCallId: id,
    state: "output-available",
    input: {},
    output: {},
  };
}
