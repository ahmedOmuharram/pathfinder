import { useCallback, useEffect, useMemo, useState, startTransition } from "react";
import type { ParamSpec } from "@pathfinder/shared";
import { getParamSpecs } from "@/lib/api/client";
import type { StrategyStep } from "@/features/strategy/types";
import { StepParamFields } from "@/features/strategy/editor/components/StepParamFields";
import {
  extractSpecVocabulary,
  extractVocabOptions,
  type VocabOption,
} from "@/features/strategy/editor/components/stepEditorUtils";
import { coerceParametersForSpecs } from "@/features/strategy/parameters/coerce";
import { Modal } from "@/lib/components/Modal";
import { Button } from "@/lib/components/ui/Button";
import { Loader2, Save } from "lucide-react";

interface ExperimentStepModalProps {
  step: StrategyStep;
  siteId: string;
  recordType: string;
  onUpdate: (updates: Partial<StrategyStep>) => void;
  onClose: () => void;
}

export function ExperimentStepModal({
  step,
  siteId,
  recordType,
  onUpdate,
  onClose,
}: ExperimentStepModalProps) {
  const [paramSpecs, setParamSpecs] = useState<ParamSpec[]>([]);
  const [loading, setLoading] = useState(false);
  const [parameters, setParameters] = useState<Record<string, unknown>>(
    step.parameters || {},
  );

  useEffect(() => {
    const searchName = step.searchName;
    if (!searchName) return;
    let cancelled = false;
    const timeout = window.setTimeout(() => {
      setLoading(true);
      getParamSpecs(siteId, recordType, searchName)
        .then((specs) => {
          if (!cancelled) {
            setParamSpecs(specs || []);
            setLoading(false);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setParamSpecs([]);
            setLoading(false);
          }
        });
    }, 100);
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [siteId, recordType, step.searchName]);

  useEffect(() => {
    startTransition(() => {
      setParameters(step.parameters || {});
    });
  }, [step.id, step.parameters]);

  const vocabOptions = useMemo(() => {
    return paramSpecs.reduce<Record<string, VocabOption[]>>((acc, spec) => {
      if (!spec.name) return acc;
      const vocabulary = extractSpecVocabulary(spec);
      if (vocabulary) {
        acc[spec.name] = extractVocabOptions(vocabulary);
      }
      return acc;
    }, {});
  }, [paramSpecs]);

  const handleSave = useCallback(() => {
    const coerced = coerceParametersForSpecs(parameters, paramSpecs, {
      allowStringParsing: false,
    });
    onUpdate({ parameters: coerced as Record<string, unknown> });
    onClose();
  }, [parameters, paramSpecs, onUpdate, onClose]);

  const isCombineStep = !!(step.primaryInputStepId && step.secondaryInputStepId);

  return (
    <Modal
      open
      onClose={onClose}
      title={step.displayName || step.searchName || "Step"}
      maxWidth="max-w-2xl"
    >
      <div className="max-h-[70vh] overflow-y-auto p-5">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Parameters
        </h4>

        {loading && (
          <div className="flex items-center gap-2 py-8 text-xs text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading parameter specs...
          </div>
        )}

        {!loading && isCombineStep && (
          <p className="py-4 text-sm text-muted-foreground">
            This is a combine step ({step.operator || "INTERSECT"}). It combines results
            from two input steps and has no searchable parameters.
          </p>
        )}

        {!loading && !isCombineStep && paramSpecs.length === 0 && (
          <p className="py-4 text-sm text-muted-foreground">
            No parameter specs found for this search.
          </p>
        )}

        {!loading && !isCombineStep && paramSpecs.length > 0 && (
          <StepParamFields
            paramSpecs={paramSpecs}
            showRaw={false}
            parameters={parameters}
            vocabOptions={vocabOptions}
            dependentOptions={{}}
            dependentLoading={{}}
            dependentErrors={{}}
            validationErrorKeys={new Set()}
            setParameters={setParameters}
          />
        )}

        <p className="mt-4 rounded border border-primary/20 bg-primary/5 p-2 text-[10px] text-primary">
          Tip: Enable &ldquo;Optimize Strategy Tree&rdquo; in the config panel to let
          the optimizer automatically tune parameters across all steps.
        </p>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
        <Button variant="outline" size="sm" onClick={onClose}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleSave}>
          <Save className="h-3 w-3" />
          Save Changes
        </Button>
      </div>
    </Modal>
  );
}
