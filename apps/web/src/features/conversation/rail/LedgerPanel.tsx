"use client";

import type { DataLedgerUpdatePayload } from "@pathfinder/shared";

import { useChatHelpersOptional } from "../runtime/chatHelpersContext";
import {
  BuildSection,
  DiscoverySection,
  FrameSection,
  IntentSection,
  PlanSection,
  SubAgentCountSection,
  VerificationSection,
} from "./LedgerPanelSections";

function latestLedger(
  messages: readonly {
    role?: string;
    parts?: readonly { type?: string; data?: unknown }[];
  }[],
): DataLedgerUpdatePayload | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const parts = messages[i]?.parts;
    if (parts === undefined) continue;
    for (let j = parts.length - 1; j >= 0; j--) {
      const part = parts[j];
      if (part?.type !== "data-ledger-update") continue;
      const data = part.data as DataLedgerUpdatePayload | undefined;
      if (data !== undefined) return data;
    }
  }
  return null;
}

export function LedgerPanel() {
  const chat = useChatHelpersOptional();
  const ledger = chat !== null ? latestLedger(chat.messages) : null;

  return (
    <div
      className="flex h-full flex-col bg-background text-foreground"
      data-testid="ledger-panel"
    >
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">Investigation Ledger</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Live state of the Lead&apos;s investigation — what&apos;s framed,
          discovered, planned, built, verified.
        </p>
      </div>
      <div className="flex-1 overflow-auto">
        {ledger === null ? (
          <p className="px-4 py-3 text-xs text-muted-foreground">
            Waiting for the Lead to dispatch its first sub-agent…
          </p>
        ) : (
          <div className="divide-y divide-border">
            <IntentSection intent={ledger.userIntent} />
            <FrameSection frame={ledger.frame} />
            <DiscoverySection discovery={ledger.discovery} />
            <PlanSection plan={ledger.plan} />
            <BuildSection build={ledger.build} />
            <VerificationSection verification={ledger.verification} />
            <SubAgentCountSection
              thisTurn={ledger.subAgentCallsThisTurn}
              total={ledger.subAgentCallsTotal}
            />
          </div>
        )}
      </div>
    </div>
  );
}
