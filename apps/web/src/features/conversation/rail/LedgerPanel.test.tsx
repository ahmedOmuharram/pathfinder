// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { DataLedgerUpdatePayload } from "@pathfinder/shared";

const messagesRef: { current: unknown[] } = { current: [] };
vi.mock("../runtime/chatHelpersContext", () => ({
  useChatHelpersOptional: () => ({ messages: messagesRef.current }),
}));

import { LedgerPanel, ledgerTabSignatures } from "./LedgerPanel";
import { useRightRailStore } from "@/state/useRightRailStore";

function makeLedger(
  overrides: Partial<DataLedgerUpdatePayload> = {},
): DataLedgerUpdatePayload {
  return {
    userIntent: {
      classification: "discovery",
      inferredGoal: "find genes",
      isDifferential: false,
      differentialSides: [],
    },
    frame: {
      present: true,
      criteriaCount: 2,
      boundCount: 2,
      openSlotCount: 0,
      droppedCount: 0,
      readyToBuild: true,
      needsUser: false,
      spec: null,
    },
    build: {
      pushedCount: 1,
      failedCount: 0,
      skippedCount: 0,
      zeroResultSteps: [],
      needsRecovery: false,
      recoveryKind: "none",
      succeeded: true,
      nodeResults: [],
    },
    verification: { complete: false, successful: false },
    constraints: { grounded: [], unmetCount: 0, blocking: false },
    subAgentCallsThisTurn: 1,
    subAgentCallsTotal: 3,
    ...overrides,
  };
}

function setLedger(ledger: DataLedgerUpdatePayload): void {
  messagesRef.current = [
    { role: "assistant", parts: [{ type: "data-ledger-update", data: ledger }] },
  ];
}

beforeEach(() => {
  useRightRailStore.setState({ ledgerSeen: {} });
  messagesRef.current = [];
});

afterEach(() => {
  cleanup();
});

describe("ledgerTabSignatures", () => {
  it("isolates a change to the tab whose section changed", () => {
    const base = ledgerTabSignatures(makeLedger());
    const buildChanged = ledgerTabSignatures(
      makeLedger({
        build: {
          pushedCount: 5,
          failedCount: 0,
          skippedCount: 0,
          zeroResultSteps: [],
          needsRecovery: false,
          recoveryKind: "none",
          succeeded: true,
          nodeResults: [],
        },
      }),
    );
    expect(buildChanged.build).not.toBe(base.build);
    expect(buildChanged.frame).toBe(base.frame);
    expect(buildChanged.verification).toBe(base.verification);
  });
});

describe("LedgerPanel tab indicators", () => {
  it("flags unseen detail tabs and not the summary tab", () => {
    setLedger(makeLedger());
    render(<LedgerPanel conversationId="c1" />);

    expect(screen.getByLabelText("Frame has updates")).toBeInTheDocument();
    expect(screen.getByLabelText("Build has updates")).toBeInTheDocument();
    expect(screen.queryByLabelText("Summary has updates")).toBeNull();
  });

  it("clears a tab's dot once viewed, leaving other tabs flagged", () => {
    setLedger(makeLedger());
    render(<LedgerPanel conversationId="c1" />);

    fireEvent.click(screen.getByRole("button", { name: /Frame/ }));
    fireEvent.click(screen.getByRole("button", { name: /Summary/ }));

    expect(screen.queryByLabelText("Frame has updates")).toBeNull();
    expect(screen.getByLabelText("Build has updates")).toBeInTheDocument();
  });
});
