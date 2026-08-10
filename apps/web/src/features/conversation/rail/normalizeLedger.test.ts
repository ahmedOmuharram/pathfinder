import { describe, expect, it } from "vitest";
import { normalizeLedgerPayload } from "./normalizeLedger";

/**
 * The ledger renders from `data-ledger-update` parts stored on past messages,
 * so the payload's shape is whatever the build that wrote it emitted. Fields
 * added since then are simply absent, and a list-valued one crashes the panel
 * on the first `.length` or `.map`.
 *
 * Reopening a conversation from June threw "Cannot read properties of
 * undefined (reading 'length')" out of the contrast list and replaced the
 * whole app with an error screen.
 */

function ledgerMissing(paths: string[]): Record<string, unknown> {
  const full: Record<string, unknown> = {
    userIntent: {
      classification: "differential",
      inferredGoal: "g",
      isDifferential: true,
      differentialSides: ["female", "male"],
    },
    frame: {
      present: true,
      criteriaCount: 1,
      boundCount: 1,
      openSlotCount: 0,
      droppedCount: 0,
      readyToBuild: true,
      needsUser: false,
      spec: {
        goal: "g",
        interpretedGoal: "g",
        recordType: "transcript",
        organismScope: null,
        title: "t",
        criteria: [],
        dropped: [],
        openSlots: [],
        readyToBuild: true,
      },
      contrasts: [],
    },
    build: {
      pushedCount: 1,
      failedCount: 0,
      skippedCount: 0,
      zeroResultSteps: [],
      needsRecovery: false,
      recoveryKind: "none",
      succeeded: true,
    },
    verification: { digest: null, status: "pending" },
    constraints: { grounded: [], unmetCount: 0, blocking: false },
    subAgentCallsThisTurn: 0,
    subAgentCallsTotal: 0,
  };
  for (const path of paths) {
    const segments = path.split(".");
    let cursor = full;
    for (const segment of segments.slice(0, -1)) {
      cursor = cursor[segment] as Record<string, unknown>;
    }
    delete cursor[segments[segments.length - 1]!];
  }
  return full;
}

describe("normalizeLedgerPayload", () => {
  it("returns null for a payload that is not an object", () => {
    expect(normalizeLedgerPayload(undefined)).toBeNull();
    expect(normalizeLedgerPayload(null)).toBeNull();
    expect(normalizeLedgerPayload("ledger")).toBeNull();
  });

  it("fills contrasts when an older snapshot predates the field", () => {
    const result = normalizeLedgerPayload(ledgerMissing(["frame.contrasts"]));

    expect(result?.frame.contrasts).toEqual([]);
  });

  it.each([
    ["userIntent.differentialSides", (l: never) => l],
    ["frame.spec.criteria", (l: never) => l],
    ["build.zeroResultSteps", (l: never) => l],
    ["constraints.grounded", (l: never) => l],
  ])("fills %s", (path) => {
    const result = normalizeLedgerPayload(ledgerMissing([path]));

    const value = path
      .split(".")
      .reduce<unknown>(
        (acc, key) => (acc as Record<string, unknown>)[key],
        result as unknown,
      );
    expect(value).toEqual([]);
  });

  it("survives every list being absent at once", () => {
    const result = normalizeLedgerPayload(
      ledgerMissing([
        "userIntent.differentialSides",
        "frame.contrasts",
        "frame.spec.criteria",
        "frame.spec.dropped",
        "frame.spec.openSlots",
        "build.zeroResultSteps",
        "constraints.grounded",
      ]),
    );

    expect(result).not.toBeNull();
    expect(result?.frame.contrasts).toEqual([]);
    expect(result?.frame.spec?.criteria).toEqual([]);
    expect(result?.build.zeroResultSteps).toEqual([]);
    expect(result?.constraints.grounded).toEqual([]);
    expect(result?.userIntent?.differentialSides).toEqual([]);
  });

  it("keeps a whole section absent rather than inventing one", () => {
    // A missing `frame` is not the same as an empty frame; the panel decides
    // what to show, but it must not be handed a fabricated section.
    const result = normalizeLedgerPayload(ledgerMissing(["userIntent"]));

    expect(result?.userIntent).toBeNull();
  });

  it("leaves populated lists untouched", () => {
    const raw = ledgerMissing([]);
    (raw["frame"] as Record<string, unknown>)["contrasts"] =[
      { criterionId: "c1", summary: "up in female vs male" },
    ];

    const result = normalizeLedgerPayload(raw);

    expect(result?.frame.contrasts).toEqual([
      { criterionId: "c1", summary: "up in female vs male" },
    ]);
  });

  it("does not treat a non-list value as a list", () => {
    const raw = ledgerMissing([]);
    (raw["frame"] as Record<string, unknown>)["contrasts"] ="nonsense";

    expect(normalizeLedgerPayload(raw)?.frame.contrasts).toEqual([]);
  });

  it("tolerates a missing verification section", () => {
    const result = normalizeLedgerPayload(ledgerMissing(["verification"]));

    expect(result).not.toBeNull();
  });

  it("tolerates a missing build section", () => {
    const result = normalizeLedgerPayload(ledgerMissing(["build"]));

    expect(result?.build.zeroResultSteps).toEqual([]);
  });
});
