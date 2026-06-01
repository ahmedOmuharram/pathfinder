export const PHASE_ROLES = [
  "lead",
  "scoping",
  "discovery",
  "planning",
  "execution",
  "verification",
] as const;

export type PhaseRole = (typeof PHASE_ROLES)[number];

export const PHASE_LABELS: Record<PhaseRole, string> = {
  lead: "Lead",
  scoping: "Scoping",
  discovery: "Discovery",
  planning: "Planning",
  execution: "Execution recovery",
  verification: "Verification",
};

export const PHASE_DESCRIPTIONS: Record<PhaseRole, string> = {
  lead: "Orchestrates the investigation and talks to you.",
  scoping: "Frames the biological problem from your message.",
  discovery: "Finds WDK searches that match the intent.",
  planning: "Authors a strategy plan from the discovered searches.",
  execution: "Repairs failed steps after a build attempt.",
  verification: "Inspects the built strategy and reports back.",
};
