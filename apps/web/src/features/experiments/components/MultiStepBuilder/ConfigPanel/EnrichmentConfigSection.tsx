import type { EnrichmentAnalysisType } from "@pathfinder/shared";
import { ENRICHMENT_ANALYSIS_LABELS } from "@/features/experiments/constants";

const ENRICHMENT_OPTIONS = (
  Object.entries(ENRICHMENT_ANALYSIS_LABELS) as [EnrichmentAnalysisType, string][]
).map(([type, label]) => ({ type, label }));

export interface EnrichmentConfigSectionProps {
  enrichments: Set<EnrichmentAnalysisType>;
  onToggleEnrichment: (type: EnrichmentAnalysisType) => void;
}

export function EnrichmentConfigSection({
  enrichments,
  onToggleEnrichment,
}: EnrichmentConfigSectionProps) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Enrichment
      </h4>
      <div className="space-y-1">
        {ENRICHMENT_OPTIONS.map((opt) => (
          <label
            key={opt.type}
            className="flex items-center gap-2 text-xs text-foreground"
          >
            <input
              type="checkbox"
              checked={enrichments.has(opt.type)}
              onChange={() => onToggleEnrichment(opt.type)}
              className="rounded border-input"
            />
            {opt.label}
          </label>
        ))}
      </div>
    </div>
  );
}
