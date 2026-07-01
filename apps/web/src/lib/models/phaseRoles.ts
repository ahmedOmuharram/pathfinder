// Mirrors the backend SSOT — pathfinder.ai.agents.roles.PhaseRole. The Lead
// orchestrates; FRAME / execution-recovery / VERIFY run as delegated sub-agents.
export const PHASE_ROLES = ["lead", "frame", "execution", "verification"] as const;

export type PhaseRole = (typeof PHASE_ROLES)[number];

export const PHASE_LABELS: Record<PhaseRole, string> = {
  lead: "Lead",
  frame: "Frame",
  execution: "Execution recovery",
  verification: "Verification",
};

export const PHASE_DESCRIPTIONS: Record<PhaseRole, string> = {
  lead: "Orchestrates the investigation and talks to you.",
  frame:
    "Operationalizes your goal into a buildable strategy spec — binds real WDK searches and resolves their parameters.",
  execution: "Repairs failed steps after a build attempt.",
  verification: "Inspects the built strategy and reports back.",
};
