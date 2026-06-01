"use client";

import { useState } from "react";
import type { DataLedgerUpdatePayload } from "@pathfinder/shared";

import { useChatHelpersOptional } from "../runtime/chatHelpersContext";
import { DiscoveryDetail } from "./DiscoveryDetail";
import {
  BuildSection,
  DiscoverySection,
  FrameSection,
  IntentSection,
  PlanSection,
  SubAgentCountSection,
  VerificationSection,
} from "./LedgerPanelSections";

type Tab = "summary" | "frame" | "discovery" | "plan" | "build" | "verification";

const TABS: { id: Tab; label: string }[] = [
  { id: "summary", label: "Summary" },
  { id: "frame", label: "Frame" },
  { id: "discovery", label: "Discovery" },
  { id: "plan", label: "Plan" },
  { id: "build", label: "Build" },
  { id: "verification", label: "Verification" },
];

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
  const [tab, setTab] = useState<Tab>("summary");

  return (
    <div
      className="flex h-full flex-col bg-background text-foreground"
      data-testid="ledger-panel"
    >
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">Investigation Ledger</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Live state of the Lead&apos;s investigation. Tabs show per-phase detail.
        </p>
      </div>
      <div className="flex shrink-0 overflow-x-auto border-b border-border bg-muted/30">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-[11px] font-medium transition-colors whitespace-nowrap ${
              tab === t.id
                ? "border-b-2 border-primary text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-auto">
        {ledger === null ? (
          <p className="px-4 py-3 text-xs text-muted-foreground">
            Waiting for the Lead to dispatch its first sub-agent…
          </p>
        ) : (
          <LedgerTabContent tab={tab} ledger={ledger} />
        )}
      </div>
    </div>
  );
}

function LedgerTabContent({
  tab,
  ledger,
}: {
  tab: Tab;
  ledger: DataLedgerUpdatePayload;
}) {
  if (tab === "summary") {
    return (
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
    );
  }
  if (tab === "frame") {
    return (
      <div className="divide-y divide-border">
        <IntentSection intent={ledger.userIntent} />
        <FrameSection frame={ledger.frame} />
      </div>
    );
  }
  if (tab === "discovery") {
    return (
      <div className="divide-y divide-border">
        <DiscoverySection discovery={ledger.discovery} />
        <DiscoveryDetail discovery={ledger.discovery} />
      </div>
    );
  }
  if (tab === "plan") {
    return (
      <div className="divide-y divide-border">
        <PlanSection plan={ledger.plan} />
      </div>
    );
  }
  if (tab === "build") {
    return (
      <div className="divide-y divide-border">
        <BuildSection build={ledger.build} />
      </div>
    );
  }
  return (
    <div className="divide-y divide-border">
      <VerificationSection verification={ledger.verification} />
    </div>
  );
}
