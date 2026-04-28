"use client";

import { Microscope, Search, Zap } from "lucide-react";

import type { Command } from "@/features/conversation/slash/types";

/**
 * Specialist + launcher commands surfaced in the slash menu.
 *
 * Per `docs/superpowers/specs/2026-04-26-specialist-commands-design.md`:
 *   - `/optimize` opens the launcher form (Phase 9). Requires ≥1 step.
 *   - `/validate` enters validate specialist mode. Requires ≥1 step.
 *   - `/research` enters research specialist mode. No precondition.
 */

const NEEDS_STEPS_REASON =
  "Strategy needs at least 1 step before this command is available.";
const SESSION_ACTIVE_REASON =
  "A specialist session is already active. Type /done to exit first.";

function reasonForStepGated(
  ctx: { stepCount: number; activeSpecialistKind?: "validate" | "research" | null },
): string | null {
  if (
    ctx.activeSpecialistKind !== undefined
    && ctx.activeSpecialistKind !== null
  ) {
    return SESSION_ACTIVE_REASON;
  }
  if (ctx.stepCount < 1) return NEEDS_STEPS_REASON;
  return null;
}

function reasonForUngated(
  ctx: { activeSpecialistKind?: "validate" | "research" | null },
): string | null {
  if (
    ctx.activeSpecialistKind !== undefined
    && ctx.activeSpecialistKind !== null
  ) {
    return SESSION_ACTIVE_REASON;
  }
  return null;
}

export const optimizeCommand: Command = {
  kind: "launcher",
  name: "optimize",
  description: "Tune a step's parameters via a sweep",
  icon: <Zap className="size-3.5 text-amber-500" aria-hidden />,
  params: [],
  disabledReason: reasonForStepGated,
};

export const validateCommand: Command = {
  kind: "specialist-enter",
  name: "validate",
  description: "Assess whether the current strategy answers your question",
  icon: <Microscope className="size-3.5 text-primary" aria-hidden />,
  params: [],
  disabledReason: reasonForStepGated,
};

export const researchCommand: Command = {
  kind: "specialist-enter",
  name: "research",
  description: "Explore biological background — literature, web, catalog",
  icon: <Search className="size-3.5 text-secondary-foreground" aria-hidden />,
  params: [],
  disabledReason: reasonForUngated,
};

export const specialistCommands: Command[] = [
  optimizeCommand,
  validateCommand,
  researchCommand,
];
