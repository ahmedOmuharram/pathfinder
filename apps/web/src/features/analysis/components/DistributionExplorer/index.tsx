import { Loader2, AlertCircle } from "lucide-react";
import type { EntityRef } from "@/features/analysis/api/stepResults";
import { useAttributeFiltering } from "@/features/analysis/hooks/useAttributeFiltering";
import { useDistributionData } from "@/features/analysis/hooks/useDistributionData";
import { useDistributionModal } from "@/features/analysis/hooks/useDistributionModal";
import { AttributeSelector } from "./AttributeSelector";
import { DistributionChart } from "./DistributionChart";

interface DistributionExplorerProps {
  entityRef: EntityRef;
}

export function DistributionExplorer({ entityRef }: DistributionExplorerProps) {
  const attrs = useAttributeFiltering(entityRef);
  const dist = useDistributionData(entityRef, attrs.selectedAttr);
  const modal = useDistributionModal(entityRef, attrs.selectedAttr);

  if (attrs.loading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading attributes...
      </div>
    );
  }

  if (attrs.error != null && attrs.attributes.length === 0) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-destructive">
        <AlertCircle className="h-4 w-4" />
        {attrs.error}
      </div>
    );
  }

  if (attrs.attributes.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No attributes with distribution data found.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <AttributeSelector
        attributes={attrs.attributes}
        selectedAttr={attrs.selectedAttr}
        onSelect={attrs.setSelectedAttr}
        onRefresh={dist.refresh}
        refreshing={dist.loading}
      />

      {dist.error != null && (
        <div className="flex items-center gap-2 text-xs text-destructive">
          <AlertCircle className="h-3.5 w-3.5" />
          {dist.error}
        </div>
      )}

      <DistributionChart
        distribution={dist.distribution}
        loading={dist.loading}
        selectedAttr={attrs.selectedAttr}
        attributes={attrs.attributes}
        modalValue={modal.modalValue}
        modalRecords={modal.modalRecords}
        loadingModal={modal.loadingModal}
        onBarClick={modal.handleBarClick}
        onCloseModal={modal.closeModal}
      />
    </div>
  );
}
