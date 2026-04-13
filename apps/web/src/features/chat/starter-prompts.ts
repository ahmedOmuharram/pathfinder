/**
 * Per-site starter prompts shown on an empty conversation.
 *
 * Pure frontend config — these never reach the backend wire format. Clicking
 * a card calls `useChat.sendMessage({ text: prompt })` which goes through
 * the normal AI SDK transport. The agent then handles the prompt like any
 * other user message; phase machine drives the rest.
 */

export interface StarterPrompt {
  title: string;
  description: string;
  prompt: string;
}

const COMMON_PROMPTS: readonly StarterPrompt[] = [
  {
    title: "Find drug targets",
    description: "Build a strategy that filters for druggable, conserved, essential genes.",
    prompt:
      "Find genes that are conserved across pathogens, essential for survival, and have predicted drug-binding sites.",
  },
  {
    title: "Compare two strains",
    description: "Identify genes differentially expressed between two strains or conditions.",
    prompt:
      "Find genes whose expression differs significantly between two strains in published microarray data.",
  },
];

const PER_SITE_PROMPTS: Record<string, readonly StarterPrompt[]> = {
  plasmodb: [
    {
      title: "Liver-stage targets",
      description: "Genes upregulated in liver vs blood stage with druggable orthologs.",
      prompt:
        "Find Plasmodium falciparum genes upregulated in liver stage compared to blood stage, that have human-druggable kinase orthologs.",
    },
    {
      title: "Vaccine candidates",
      description: "Surface-exposed, conserved-across-strains, immunogenic proteins.",
      prompt:
        "Find Plasmodium genes encoding surface proteins that are conserved across all P. falciparum strains and have known immunogenic epitopes.",
    },
  ],
  toxodb: [
    {
      title: "Apicoplast-targeted",
      description: "Genes with apicoplast targeting peptides essential for the parasite.",
      prompt:
        "Find Toxoplasma gondii genes with predicted apicoplast targeting peptides that are essential for tachyzoite growth.",
    },
  ],
  cryptodb: [
    {
      title: "Drug-target prioritization",
      description: "Cryptosporidium genes with no human ortholog plus essentiality data.",
      prompt:
        "Find Cryptosporidium parvum genes that lack a human ortholog and are predicted to be essential.",
    },
  ],
  giardiadb: [
    {
      title: "Encystation regulators",
      description: "Transcription factors upregulated during Giardia encystation.",
      prompt:
        "Find Giardia lamblia transcription factors that are upregulated during encystation.",
    },
  ],
  trichdb: [
    {
      title: "Surface antigens",
      description: "Trichomonas surface-exposed proteins under host pressure.",
      prompt:
        "Find Trichomonas vaginalis surface-exposed proteins with signs of positive selection.",
    },
  ],
  tritrypdb: [
    {
      title: "Trypanosome essential kinases",
      description: "Kinases essential in the bloodstream form with no human ortholog.",
      prompt:
        "Find Trypanosoma brucei kinases that are essential in the bloodstream stage and lack a close human ortholog.",
    },
  ],
  fungidb: [
    {
      title: "Resistance markers",
      description: "Fungal genes whose mutations confer drug resistance.",
      prompt:
        "Find Candida albicans genes whose mutations are linked to azole resistance in clinical isolates.",
    },
  ],
  hostdb: [
    {
      title: "Host immune response",
      description: "Host genes upregulated during infection across studies.",
      prompt:
        "Find host genes consistently upregulated during malaria infection across multiple transcriptomic studies.",
    },
  ],
  microsporidiadb: [
    {
      title: "Genome reduction targets",
      description: "Conserved Microsporidia genes lost in the most reduced genomes.",
      prompt:
        "Find Microsporidia genes conserved across all sequenced species except those with the most reduced genomes.",
    },
  ],
  piroplasmadb: [
    {
      title: "Piroplasm comparative",
      description: "Babesia/Theileria-conserved, host-divergent genes.",
      prompt:
        "Find genes conserved across Babesia and Theileria but absent in mammalian hosts.",
    },
  ],
  amoebadb: [
    {
      title: "Cyst-stage essentiality",
      description: "Entamoeba genes essential for cyst formation.",
      prompt:
        "Find Entamoeba histolytica genes upregulated during cyst formation that are predicted to be essential.",
    },
  ],
  vectorbase: [
    {
      title: "Insecticide resistance",
      description: "Anopheles genes linked to pyrethroid resistance.",
      prompt:
        "Find Anopheles gambiae genes whose expression or mutations are linked to pyrethroid resistance.",
    },
  ],
};

const EXPERIMENT_PROMPTS: readonly StarterPrompt[] = [
  {
    title: "Explain this experiment",
    description: "Walk me through the metrics, gene lists, and what they mean.",
    prompt: "Walk me through this experiment: explain the metrics, the top false positives, and what the result tells us about the gene set.",
  },
  {
    title: "Suggest improvements",
    description: "Propose changes to the search to lift the F1 score.",
    prompt: "Suggest changes to the search strategy that would improve the F1 score for this experiment.",
  },
  {
    title: "Compare to baseline",
    description: "Run the same gene set against a stricter baseline strategy.",
    prompt: "Compare this experiment's results to a baseline strategy with no filters, and explain the lift.",
  },
];

export function getStarterPrompts(
  siteId: string,
  mode: "strategy" | "experiment",
): readonly StarterPrompt[] {
  if (mode === "experiment") return EXPERIMENT_PROMPTS;
  const siteSpecific = PER_SITE_PROMPTS[siteId.toLowerCase()] ?? [];
  return [...siteSpecific, ...COMMON_PROMPTS];
}
