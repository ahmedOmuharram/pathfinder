// Mirrors the backend SSOT - pathfinder.ai.agents.roles.PhaseRole. The Lead
// orchestrates; FRAME / execution-recovery / VERIFY run as delegated sub-agents.
export const PHASE_ROLES = ["lead", "frame", "execution", "verification"] as const;

export type PhaseRole = (typeof PHASE_ROLES)[number];

// Keyed by the phase strings the wire carries, so a sub-agent group and the
// settings row read the same label. `execution` is the name older logs use for
// the build phase.
export const PHASE_LABELS: Record<string, string> = {
  lead: "Lead",
  frame: "Frame",
  build: "Build",
  execution: "Build",
  verification: "Verification",
  recover_failed_steps: "Recovery",
};

export const PHASE_DESCRIPTIONS: Record<PhaseRole, string> = {
  lead: "Orchestrates the investigation and talks to you.",
  frame:
    "Operationalizes your goal into a buildable strategy spec - binds real WDK searches and resolves their parameters.",
  execution: "Repairs failed steps after a build attempt.",
  verification: "Inspects the built strategy and reports back.",
};
