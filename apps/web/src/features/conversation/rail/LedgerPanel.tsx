"use client";

import { useState } from "react";
import type { DataLedgerUpdatePayload, PlanArtifact } from "@pathfinder/shared";

import { cn } from "@/lib/utils/cn";
import { useRightRailStore } from "@/state/useRightRailStore";

import { useChatHelpersOptional } from "../runtime/chatHelpersContext";
import { DataPlanArtifact } from "../content/parts/DataPlanArtifact";
import { latestPlanAcross } from "../content/parts/planCarouselData";
import { ConstraintsSection } from "./ConstraintsSection";
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
type DetailTab = Exclude<Tab, "summary">;

const TABS: { id: Tab; label: string }[] = [
  { id: "summary", label: "Summary" },
  { id: "frame", label: "Frame" },
  { id: "discovery", label: "Discovery" },
  { id: "plan", label: "Plan" },
  { id: "build", label: "Build" },
  { id: "verification", label: "Verification" },
];

export function ledgerTabSignatures(
  ledger: DataLedgerUpdatePayload,
): Record<DetailTab, string> {
  return {
    frame: JSON.stringify([ledger.userIntent, ledger.frame]),
    discovery: JSON.stringify(ledger.discovery),
    plan: JSON.stringify(ledger.plan),
    build: JSON.stringify(ledger.build),
    verification: JSON.stringify(ledger.verification),
  };
}

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

export function LedgerPanel({ conversationId }: { conversationId: string }) {
  const chat = useChatHelpersOptional();
  const ledger = chat !== null ? latestLedger(chat.messages) : null;
  const planArtifact = chat !== null ? latestPlanAcross(chat.messages) : null;
  const [tab, setTab] = useState<Tab>("summary");
  const ledgerSeen = useRightRailStore((s) => s.ledgerSeen);
  const markLedgerTabSeen = useRightRailStore((s) => s.markLedgerTabSeen);

  const signatures = ledger !== null ? ledgerTabSignatures(ledger) : null;
  const seen = ledgerSeen[conversationId] ?? {};

  // Keep the active detail tab marked seen as it updates live (render-time
  // pattern, no useEffect) so it never re-flags after the user watched it.
  if (signatures !== null && tab !== "summary" && seen[tab] !== signatures[tab]) {
    const activeSig = signatures[tab];
    queueMicrotask(() => markLedgerTabSeen(conversationId, tab, activeSig));
  }

  const selectTab = (next: Tab) => {
    setTab(next);
    if (signatures !== null && next !== "summary") {
      markLedgerTabSeen(conversationId, next, signatures[next]);
    }
  };

  const hasUpdate = (id: Tab): boolean =>
    signatures !== null && id !== "summary" && seen[id] !== signatures[id];

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
      <div className="grid shrink-0 grid-cols-3 gap-0.5 border-b border-border bg-muted/30 p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => selectTab(t.id)}
            className={cn(
              "relative rounded-md px-2 py-1.5 text-[11px] font-medium transition-colors",
              tab === t.id
                ? "bg-card text-primary shadow-xs"
                : "text-muted-foreground hover:bg-card/60 hover:text-foreground",
            )}
          >
            {t.label}
            {hasUpdate(t.id) && t.id !== tab && (
              <span
                aria-label={`${t.label} has updates`}
                className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-primary"
              />
            )}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-auto">
        {ledger === null ? (
          <p className="px-4 py-3 text-xs text-muted-foreground">
            Waiting for the Lead to dispatch its first sub-agent...
          </p>
        ) : (
          <LedgerTabContent tab={tab} ledger={ledger} planArtifact={planArtifact} />
        )}
      </div>
    </div>
  );
}

function LedgerTabContent({
  tab,
  ledger,
  planArtifact,
}: {
  tab: Tab;
  ledger: DataLedgerUpdatePayload;
  planArtifact: PlanArtifact | null;
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
        <ConstraintsSection constraints={ledger.constraints} />
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
        {planArtifact !== null && (
          <div className="p-3">
            <DataPlanArtifact data={planArtifact} />
          </div>
        )}
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
      <ConstraintsSection constraints={ledger.constraints} />
    </div>
  );
}
