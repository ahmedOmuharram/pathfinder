/**
 * The shapes the buildTrace acceptance modules read.
 * Frozen with the buildTrace acceptance modules: implementers may not touch tests/acceptance/**.
 */
export interface Chunk {
  readonly type: string;
  readonly [field: string]: unknown;
}

export interface TraceRowShape {
  key: string;
  toolCallId: string;
  toolName: string;
  summary: string | null;
  status: string;
  input: unknown;
  output: unknown;
  errorText: string | null;
}

export interface TraceGroupShape {
  key: string;
  phase: string;
  rows: TraceRowShape[];
  tokens: number;
  costUsd: string;
  state: string;
}

export interface TraceShape {
  groups: TraceGroupShape[];
  figures: { type: string }[];
  rowCount: number;
  running: boolean;
}

export interface ClientApi {
  buildTrace: (
    parts: readonly unknown[],
    options?: { renderingKinds?: ReadonlySet<string> },
  ) => TraceShape[];
  reduceTurn: (chunks: readonly Chunk[]) => { parts: unknown[] };
}
