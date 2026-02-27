import { useEffect, useState } from "react";
import { requestJson } from "@/lib/api/http";
import { Modal } from "@/lib/components/Modal";
import { Button } from "@/lib/components/ui/Button";
import { Import, Loader2 } from "lucide-react";
import type { StrategyStep } from "@/features/strategy/types";
import type { CombineOperator } from "@pathfinder/shared";

interface ImportableStrategy {
  wdkStrategyId: number;
  name: string;
  recordType: string;
  stepCount: number | null;
  estimatedSize: number | null;
  lastModified: string | null;
  isSaved: boolean;
}

interface StrategyImportModalProps {
  open: boolean;
  siteId: string;
  onImport: (steps: StrategyStep[], name: string, recordType: string) => void;
  onClose: () => void;
}

const WDK_OPERATOR_MAP: Record<string, CombineOperator> = {
  INTERSECT: "INTERSECT",
  UNION: "UNION",
  MINUS: "MINUS",
  LMINUS: "MINUS",
  RMINUS: "RMINUS",
  LONLY: "MINUS",
  RONLY: "RMINUS",
};

/**
 * Recursively walk the enriched WDK stepTree and extract flat StrategyStep
 * objects.  The backend enriches each tree node with ``searchName``,
 * ``displayName``, ``parameters``, ``recordType`` from the WDK steps map so
 * we can read them directly off the node.
 *
 * For combine steps (those with both ``primaryInput`` and ``secondaryInput``),
 * the WDK boolean operator is stored in ``parameters.bq_operator``.  We map it
 * to our ``CombineOperator`` type so ``serializeStrategyPlan`` can build a
 * valid plan.
 */
function flattenEnrichedTree(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  node: any,
  fallbackRecordType: string,
): StrategyStep[] {
  if (!node) return [];
  const results: StrategyStep[] = [];

  const primaryInput = node.primaryInput;
  const secondaryInput = node.secondaryInput;

  if (primaryInput) {
    results.push(...flattenEnrichedTree(primaryInput, fallbackRecordType));
  }
  if (secondaryInput) {
    results.push(...flattenEnrichedTree(secondaryInput, fallbackRecordType));
  }

  const stepId = node.stepId;
  const searchName = node.searchName || "";
  const displayName = node.displayName || searchName || `Step ${stepId}`;
  const parameters = node.parameters || {};
  const recordType = node.recordType || fallbackRecordType;
  const estimatedSize = node.estimatedSize;

  const isCombine = Boolean(primaryInput && secondaryInput);
  let operator: CombineOperator | undefined;
  if (isCombine) {
    const wdkOp = (parameters.bq_operator ?? "").toString().toUpperCase();
    operator = WDK_OPERATOR_MAP[wdkOp] ?? "INTERSECT";
  }

  const step: StrategyStep = {
    id: `imported_${stepId}`,
    displayName,
    searchName,
    recordType,
    parameters,
    resultCount: typeof estimatedSize === "number" ? estimatedSize : null,
    wdkStepId: typeof stepId === "number" ? stepId : undefined,
    operator,
    primaryInputStepId: primaryInput ? `imported_${primaryInput.stepId}` : undefined,
    secondaryInputStepId: secondaryInput
      ? `imported_${secondaryInput.stepId}`
      : undefined,
  };

  results.push(step);
  return results;
}

export function StrategyImportModal({
  open,
  siteId,
  onImport,
  onClose,
}: StrategyImportModalProps) {
  const [strategies, setStrategies] = useState<ImportableStrategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    requestJson<ImportableStrategy[]>(
      `/api/v1/experiments/importable-strategies?siteId=${encodeURIComponent(siteId)}`,
    )
      .then(setStrategies)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [open, siteId]);

  const handleImport = async (strategyId: number) => {
    setImporting(strategyId);
    setError(null);
    try {
      const detail = await requestJson<{
        name: string;
        recordType: string;
        stepTree: unknown;
        steps: unknown[];
      }>(
        `/api/v1/experiments/importable-strategies/${strategyId}/details?siteId=${encodeURIComponent(siteId)}`,
      );

      const imported = flattenEnrichedTree(
        detail.stepTree,
        detail.recordType || "gene",
      );

      if (imported.length === 0) {
        setError("Strategy has no steps to import.");
        return;
      }

      onImport(
        imported,
        detail.name || "Imported strategy",
        detail.recordType || "gene",
      );
    } catch (err) {
      setError(String(err));
    } finally {
      setImporting(null);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Import Strategy">
      <div className="max-h-96 min-h-48 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && (
          <div className="mb-3 rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}

        {!loading && strategies.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No strategies found. Create strategies from the chat tab first.
          </p>
        )}

        {strategies.map((strat) => (
          <div
            key={strat.wdkStrategyId}
            className="flex items-center justify-between border-b border-border px-3 py-3 last:border-b-0"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">
                {strat.name || `Strategy #${strat.wdkStrategyId}`}
              </p>
              <p className="text-xs text-muted-foreground">
                {strat.recordType || "unknown"} &middot; {strat.stepCount ?? "?"} steps
                &middot; {strat.estimatedSize?.toLocaleString() ?? "?"} results
                {strat.isSaved && " (saved)"}
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void handleImport(strat.wdkStrategyId)}
              disabled={importing !== null}
              loading={importing === strat.wdkStrategyId}
            >
              <Import className="h-3 w-3" />
              Import
            </Button>
          </div>
        ))}
      </div>
    </Modal>
  );
}
