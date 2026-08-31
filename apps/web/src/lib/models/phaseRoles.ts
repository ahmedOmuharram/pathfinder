// Mirrors the backend SSOT - pathfinder.ai.agents.roles.PhaseRole.
export const PHASE_ROLES = ["lead", "frame", "execution", "verification"] as const;

export type PhaseRole = (typeof PHASE_ROLES)[number];

// Keyed by the phase strings the wire carries, so a trace group and the
// settings row read the same label. `execution` is the name older logs use for
// the build phase.
export const PHASE_LABELS: Record<string, string> = {
  lead: "Assistant",
  frame: "Planning",
  build: "Building",
  execution: "Building",
  verification: "Checking",
  recover_failed_steps: "Repairing",
};

export function phaseLabel(phase: string): string {
  return PHASE_LABELS[phase] ?? phase;
}

export const PHASE_DESCRIPTIONS: Record<PhaseRole, string> = {
  lead: "Talks with you and decides what happens next.",
  frame: "Turns your question into a plan of searches and fills in their settings.",
  execution: "Builds the strategy and repairs any step the site refuses.",
  verification: "Checks the built strategy and reports what it found.",
};
