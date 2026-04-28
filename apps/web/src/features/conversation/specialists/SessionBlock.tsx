"use client";

import { ChevronDown, ChevronRight, Microscope, Search } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { SpecialistKind } from "@pathfinder/shared";
import { cn } from "@/lib/utils/cn";

const KIND_LABEL: Record<SpecialistKind, string> = {
  validate: "Validate",
  research: "Research",
};

const KIND_TINT: Record<SpecialistKind, string> = {
  validate: "border-primary/40 bg-primary/10",
  research: "border-secondary-foreground/20 bg-secondary",
};

const KIND_HEADER_HOVER: Record<SpecialistKind, string> = {
  validate: "hover:bg-primary/15",
  research: "hover:bg-secondary/80",
};

const KIND_DIVIDER: Record<SpecialistKind, string> = {
  validate: "border-primary/30",
  research: "border-secondary-foreground/15",
};

export interface SessionBlockProps {
  kind: SpecialistKind;
  enteredAt: string;
  /** Null until the session has emitted its `data-specialist-exited` part. */
  exitedAt: string | null;
  /** The grouped child messages emitted between entered/exited parts. */
  children: ReactNode;
  /** Optional one-line summary shown when collapsed. Defaults to the kind label. */
  collapsedSummary?: string;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function SessionBlock({
  kind,
  enteredAt,
  exitedAt,
  children,
  collapsedSummary,
}: SessionBlockProps) {
  // Start collapsed if the session is already exited at first render.
  // Auto-collapse the first time `exitedAt` transitions to non-null
  // mid-mount, but the user can re-expand and the collapse won't fire
  // again.
  const [expanded, setExpanded] = useState(exitedAt === null);
  const [seenExit, setSeenExit] = useState(exitedAt !== null);
  if (exitedAt !== null && !seenExit) {
    setSeenExit(true);
    setExpanded(false);
  }

  const Icon = kind === "validate" ? Microscope : Search;
  const headerLabel = `${KIND_LABEL[kind]} session — entered ${formatTime(
    enteredAt,
  )}${exitedAt !== null ? ` · exited ${formatTime(exitedAt)}` : " · running…"}`;

  return (
    <div
      data-testid="specialist-session-block"
      data-kind={kind}
      data-expanded={expanded ? "true" : "false"}
      className={cn("my-3 rounded-md border", KIND_TINT[kind])}
    >
      <button
        type="button"
        data-testid="specialist-session-toggle"
        onClick={() => setExpanded((prev) => !prev)}
        className={cn(
          "flex w-full items-center gap-2 px-3 py-2 text-left text-xs",
          KIND_HEADER_HOVER[kind],
        )}
      >
        {expanded ? (
          <ChevronDown className="size-3.5" aria-hidden />
        ) : (
          <ChevronRight className="size-3.5" aria-hidden />
        )}
        <Icon className="size-3.5" aria-hidden />
        <span className="font-medium">{headerLabel}</span>
        {!expanded && collapsedSummary !== undefined ? (
          <span className="ml-2 truncate opacity-70">
            {collapsedSummary}
          </span>
        ) : null}
      </button>
      {expanded ? (
        <div
          data-testid="specialist-session-body"
          className={cn("border-t px-3 py-2", KIND_DIVIDER[kind])}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
