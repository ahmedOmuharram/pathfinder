"use client";

import { Cloud } from "lucide-react";

import {
  useOrchestratorStore,
  type SupervisorEvent,
  type SupervisorEventKind,
} from "@/state/useOrchestratorStore";

import { RailEmptyState, RailPanelShell } from "./RailPanelShell";

const KIND_LABEL: Record<SupervisorEventKind, string> = {
  phase_enter: "phase enter",
  phase_exit: "phase exit",
  ejection: "ejection",
  approval: "approval",
  deny: "deny",
  plan_event: "plan",
  build_outcome: "build",
  supervisor_note: "note",
  route: "route",
  summary: "summary",
};

const KIND_COLOR: Record<SupervisorEventKind, string> = {
  phase_enter: "text-blue-500",
  phase_exit: "text-blue-400",
  ejection: "text-red-500",
  approval: "text-green-500",
  deny: "text-orange-500",
  plan_event: "text-purple-500",
  build_outcome: "text-purple-400",
  supervisor_note: "text-amber-500",
  route: "text-sky-500",
  summary: "text-muted-foreground",
};

export function OrchestratorPanel() {
  const events = useOrchestratorStore((s) => s.events);
  return (
    <RailPanelShell title="Orchestrator">
      {events.length === 0 ? (
        <RailEmptyState
          icon={<Cloud className="h-8 w-8" aria-hidden />}
          heading="Quiet for now"
          description="The orchestrator's running context appears here as phases hand off, plans are approved, and notes are journaled."
        />
      ) : (
        <ol className="divide-y divide-border">
          {events.map((event, idx) => (
            <EventRow key={`${event.at}-${idx}`} event={event} />
          ))}
        </ol>
      )}
    </RailPanelShell>
  );
}

function EventRow({ event }: { event: SupervisorEvent }) {
  return (
    <li className="px-3 py-2">
      <div className="flex items-baseline gap-2">
        <span
          className={`text-[10px] font-semibold uppercase tracking-wider ${KIND_COLOR[event.kind]}`}
        >
          {KIND_LABEL[event.kind]}
        </span>
        {event.phase != null && (
          <span className="text-[10px] text-muted-foreground">
            {event.phase}
          </span>
        )}
        <span className="ml-auto text-[10px] text-muted-foreground">
          {formatTime(event.at)}
        </span>
      </div>
      <p className="mt-0.5 text-xs">{event.summary}</p>
      {event.detail != null && event.detail.length > 0 && (
        <p className="mt-0.5 whitespace-pre-wrap text-[11px] text-muted-foreground">
          {event.detail}
        </p>
      )}
    </li>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
