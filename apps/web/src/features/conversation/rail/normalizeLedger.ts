import type {
  DataLedgerUpdatePayload,
  LedgerBuildPayload,
  LedgerConstraintsPayload,
  LedgerFramePayload,
  LedgerIntentPayload,
  LedgerSpecPayload,
} from "@pathfinder/shared";

/**
 * Make a stored ledger snapshot safe to render.
 *
 * The panel reads `data-ledger-update` parts off past messages, so a payload
 * is only as new as the build that wrote it. A list added after a snapshot was
 * written is absent rather than empty, and the first `.length` on it takes down
 * the whole app. Every list is refilled here, once, so the components keep
 * their non-optional types.
 *
 * Sections are left null when absent instead of being fabricated: "no intent
 * recorded" and "an intent with nothing in it" are different states, and only
 * the panel should decide how to show the difference.
 */

function record(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function list<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function spec(raw: unknown): LedgerSpecPayload | null {
  const source = record(raw);
  if (source === null) return null;
  return {
    ...source,
    criteria: list(source["criteria"]),
    dropped: list(source["dropped"]),
    openSlots: list(source["openSlots"]),
  } as unknown as LedgerSpecPayload;
}

function frame(raw: unknown): LedgerFramePayload {
  const source = record(raw) ?? {};
  return {
    ...source,
    spec: spec(source["spec"]),
    contrasts: list(source["contrasts"]),
  } as unknown as LedgerFramePayload;
}

function build(raw: unknown): LedgerBuildPayload {
  const source = record(raw) ?? {};
  return {
    ...source,
    zeroResultSteps: list(source["zeroResultSteps"]),
  } as unknown as LedgerBuildPayload;
}

function constraints(raw: unknown): LedgerConstraintsPayload {
  const source = record(raw) ?? {};
  return {
    ...source,
    grounded: list(source["grounded"]),
  } as unknown as LedgerConstraintsPayload;
}

function intent(raw: unknown): LedgerIntentPayload | null {
  const source = record(raw);
  if (source === null) return null;
  return {
    ...source,
    differentialSides: list(source["differentialSides"]),
  } as unknown as LedgerIntentPayload;
}

export function normalizeLedgerPayload(raw: unknown): DataLedgerUpdatePayload | null {
  const source = record(raw);
  if (source === null) return null;
  return {
    ...source,
    userIntent: intent(source["userIntent"]),
    frame: frame(source["frame"]),
    build: build(source["build"]),
    constraints: constraints(source["constraints"]),
  } as unknown as DataLedgerUpdatePayload;
}
