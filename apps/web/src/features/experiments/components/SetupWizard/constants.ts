export const STEPS = ["Search", "Parameters", "Controls", "Run"] as const;
export type WizardStep = (typeof STEPS)[number];

export const GENE_RECORD_TYPES = new Set(["gene", "transcript"]);
