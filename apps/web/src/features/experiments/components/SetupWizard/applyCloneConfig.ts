import type { ExperimentConfig, EnrichmentAnalysisType } from "@pathfinder/shared";
import type { ResolvedGene } from "@/lib/api/client";

export interface ApplyCloneSetters {
  setSelectedRecordType: (v: string) => void;
  setSelectedSearch: (v: string) => void;
  setName: (v: string) => void;
  setEnableCV: (v: boolean) => void;
  setKFolds: (v: number) => void;
  setKFoldsDraft: (v: string) => void;
  setEnrichments: (v: Set<EnrichmentAnalysisType>) => void;
  setPositiveGenes: (v: ResolvedGene[]) => void;
  setNegativeGenes: (v: ResolvedGene[]) => void;
}

export function applyCloneConfig(
  config: ExperimentConfig,
  setters: ApplyCloneSetters,
): Record<string, unknown> {
  const {
    setSelectedRecordType,
    setSelectedSearch,
    setName,
    setEnableCV,
    setKFolds,
    setKFoldsDraft,
    setEnrichments,
    setPositiveGenes,
    setNegativeGenes,
  } = setters;

  setSelectedRecordType(config.recordType);
  setSelectedSearch(config.searchName);
  setName(`${config.name} (clone)`);
  setEnableCV(config.enableCrossValidation);
  setKFolds(config.kFolds);
  setKFoldsDraft(String(config.kFolds));
  setEnrichments(new Set(config.enrichmentTypes));

  const toResolved = (ids: string[]): ResolvedGene[] =>
    ids.map((id) => ({
      geneId: id,
      displayName: id,
      organism: "",
      product: "",
      geneName: "",
      geneType: "",
      location: "",
    }));
  setPositiveGenes(toResolved(config.positiveControls));
  setNegativeGenes(toResolved(config.negativeControls));

  return config.parameters;
}
