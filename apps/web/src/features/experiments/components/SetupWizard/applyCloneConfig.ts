import type { ExperimentConfig, EnrichmentAnalysisType } from "@pathfinder/shared";

export interface ApplyCloneSetters {
  setSelectedRecordType: (v: string) => void;
  setSelectedSearch: (v: string) => void;
  setName: (v: string) => void;
  setEnableCV: (v: boolean) => void;
  setKFolds: (v: number) => void;
  setKFoldsDraft: (v: string) => void;
  setEnrichments: (v: Set<EnrichmentAnalysisType>) => void;
  setPositiveGenes: (v: { geneId: string }[]) => void;
  setNegativeGenes: (v: { geneId: string }[]) => void;
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

  const toResolved = (ids: string[]): { geneId: string }[] =>
    ids.map((id) => ({ geneId: id }));
  setPositiveGenes(toResolved(config.positiveControls));
  setNegativeGenes(toResolved(config.negativeControls));

  return config.parameters;
}
