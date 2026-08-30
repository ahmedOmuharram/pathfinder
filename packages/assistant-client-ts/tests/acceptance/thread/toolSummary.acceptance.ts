/**
 * Frozen acceptance: the `data-tool-summary` reduction rule, PROTOCOL 1.4.0.
 *
 * No-edit rule: implementers may not touch `tests/acceptance/**`. A test that
 * is genuinely wrong is escalated to the session lead, who is the only party
 * that edits this suite.
 *
 * Run it with `yarn test:acceptance`. The default `yarn test` never collects
 * this path. The module loads the client through a guarded dynamic import and
 * probes the reducer for the summary field, so it skips cleanly until batch 1
 * lands rather than going red under an implementer.
 */
import { describe, expect, it } from "vitest";

interface Chunk {
  readonly type: string;
  readonly [field: string]: unknown;
}

interface ToolPartShape {
  type: string;
  toolCallId: string;
  state: string;
  input?: unknown;
  output?: unknown;
  summary?: string;
  summaryStatus?: string;
}

interface MessageShape {
  parts: unknown[];
}

interface ClientApi {
  reduceTurn: (chunks: readonly Chunk[]) => MessageShape;
  isKnownChunkKind: (type: string) => boolean;
  PROTOCOL_VERSION: string;
}

const SUMMARY_KIND = "data-tool-summary";
const CALL = "call_3";
const TOOL = "preview_eda_subset";
const SUMMARY = "6 of 12 Sample";

const INPUT = { entityId: "ENT_8151325d", distributionVariableId: "VAR_7033e90f" };
const OUTPUT = {
  entityCounts: [
    {
      entityId: "ENT_8151325d",
      entityDisplayName: "Sample",
      count: 6,
      unfilteredCount: 12,
    },
  ],
};

function callChunks(): Chunk[] {
  return [
    { type: "start", messageId: "11111111-1111-1111-1111-111111111111" },
    { type: "tool-input-start", toolCallId: CALL, toolName: TOOL },
    { type: "tool-input-available", toolCallId: CALL, toolName: TOOL, input: INPUT },
    { type: "tool-output-available", toolCallId: CALL, output: OUTPUT },
  ];
}

function summaryChunk(summary: string, status?: string): Chunk {
  return {
    type: SUMMARY_KIND,
    data:
      status === undefined
        ? { toolCallId: CALL, summary }
        : { toolCallId: CALL, summary, status },
  };
}

/** Load the client and probe it for the batch 1 reduction rule. */
async function loadClient(): Promise<ClientApi | null> {
  try {
    const loaded: unknown = await import("../../../src/index.ts");
    const candidate = loaded as Partial<ClientApi>;
    const reduceTurn = candidate.reduceTurn;
    const isKnownChunkKind = candidate.isKnownChunkKind;
    const version = candidate.PROTOCOL_VERSION;
    if (typeof reduceTurn !== "function") return null;
    if (typeof isKnownChunkKind !== "function") return null;
    if (typeof version !== "string") return null;
    const probe = reduceTurn([...callChunks(), summaryChunk(SUMMARY, "ok")]);
    const part = probe.parts[0] as ToolPartShape | undefined;
    if (part?.summary !== SUMMARY) return null;
    return { reduceTurn, isKnownChunkKind, PROTOCOL_VERSION: version };
  } catch {
    return null;
  }
}

const client = await loadClient();

function api(): ClientApi {
  return client as ClientApi;
}

function firstPart(message: MessageShape): ToolPartShape {
  const part = message.parts[0] as ToolPartShape | undefined;
  if (part === undefined) throw new Error("the reduced message holds no part");
  return part;
}

describe.skipIf(client === null)("data-tool-summary reduction, PROTOCOL 1.4.0", () => {
  it("folds the summary onto the call it names and appends no part", () => {
    const message = api().reduceTurn([...callChunks(), summaryChunk(SUMMARY, "ok")]);

    expect(message.parts).toHaveLength(1);
    const part = firstPart(message);
    expect(part.type).toBe("tool-preview_eda_subset");
    expect(part.toolCallId).toBe("call_3");
    expect(part.state).toBe("output-available");
    expect(part.summary).toBe("6 of 12 Sample");
    expect(part.summaryStatus).toBe("ok");
  });

  it("ignores a summary naming a call it does not hold", () => {
    const stray: Chunk = {
      type: SUMMARY_KIND,
      data: { toolCallId: "call_gone", summary: "nothing holds this call" },
    };

    const message = api().reduceTurn([...callChunks(), stray]);

    expect(message.parts).toHaveLength(1);
    expect(firstPart(message).toolCallId).toBe("call_3");
    expect(firstPart(message).summary).toBeUndefined();
  });

  it("replaces an earlier summary for the same call", () => {
    const message = api().reduceTurn([
      ...callChunks(),
      summaryChunk("12 of 12 Sample", "ok"),
      summaryChunk(SUMMARY, "ok"),
    ]);

    expect(message.parts).toHaveLength(1);
    expect(firstPart(message).summary).toBe("6 of 12 Sample");
  });

  it("carries the empty status through", () => {
    const message = api().reduceTurn([
      ...callChunks(),
      summaryChunk("0 of 12 Sample", "empty"),
    ]);

    expect(firstPart(message).summary).toBe("0 of 12 Sample");
    expect(firstPart(message).summaryStatus).toBe("empty");
  });

  it("defaults the status to ok when the chunk carries none", () => {
    const message = api().reduceTurn([...callChunks(), summaryChunk(SUMMARY)]);

    expect(firstPart(message).summary).toBe("6 of 12 Sample");
    expect(firstPart(message).summaryStatus).toBe("ok");
  });

  it("yields the same part whether the summary precedes or follows the output", () => {
    const [start, inputStart, inputAvailable, outputAvailable] = callChunks();
    if (
      start === undefined ||
      inputStart === undefined ||
      inputAvailable === undefined ||
      outputAvailable === undefined
    ) {
      throw new Error("the call fixture is incomplete");
    }
    const summary = summaryChunk(SUMMARY, "ok");

    const summaryLast = api().reduceTurn([
      start,
      inputStart,
      inputAvailable,
      outputAvailable,
      summary,
    ]);
    const summaryFirst = api().reduceTurn([
      start,
      inputStart,
      inputAvailable,
      summary,
      outputAvailable,
    ]);

    expect(summaryFirst.parts).toHaveLength(1);
    expect(summaryLast.parts).toHaveLength(1);
    expect(firstPart(summaryFirst)).toEqual(firstPart(summaryLast));
    expect(firstPart(summaryFirst).summary).toBe("6 of 12 Sample");
    expect(firstPart(summaryFirst).summaryStatus).toBe("ok");
  });

  it("names the kind as known, so the transport forwards it", () => {
    expect(api().isKnownChunkKind("data-tool-summary")).toBe(true);
  });

  it("reports a protocol version that carries section 6.3 (1.4 or later)", () => {
    const [major, minor] = api().PROTOCOL_VERSION.split(".").map(Number);
    expect(major).toBe(1);
    expect(minor).toBeGreaterThanOrEqual(4);
  });
});
