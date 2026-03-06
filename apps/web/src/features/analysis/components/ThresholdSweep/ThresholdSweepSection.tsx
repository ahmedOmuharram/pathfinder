import { useState, useMemo, useCallback, useRef } from "react";
import type { Experiment } from "@pathfinder/shared";
import { Play, Loader2, Square } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import {
  streamThresholdSweep,
  type ThresholdSweepPoint,
  type ThresholdSweepResult,
  type SweepRequest,
} from "@/features/workbench/api";
import { useParamSpecs } from "../../hooks/useParamSpecs";
import {
  isOptimizable,
  isNumericParam,
  isMultiPickParam,
  flattenVocab,
} from "../../utils/paramUtils";
import type { SweepableParam } from "./types";
import { fmtNum } from "./types";
import { CategoricalPicker } from "./CategoricalPicker";
import { SweepChart } from "./SweepChart";
import { SweepSummary } from "./SweepSummary";
import { SweepTable } from "./SweepTable";

interface ThresholdSweepSectionProps {
  experiment: Experiment;
}

export function ThresholdSweepSection({ experiment }: ThresholdSweepSectionProps) {
  const { siteId, recordType, searchName } = experiment.config;
  const { paramSpecs, isLoading: specsLoading } = useParamSpecs(
    siteId,
    recordType,
    searchName,
  );

  const [paramName, setParamName] = useState("");
  const [minVal, setMinVal] = useState("");
  const [maxVal, setMaxVal] = useState("");
  const [steps, setSteps] = useState("10");
  const [selectedValues, setSelectedValues] = useState<Set<string>>(new Set());

  const [livePoints, setLivePoints] = useState<ThresholdSweepPoint[]>([]);
  const [completedCount, setCompletedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [finalResult, setFinalResult] = useState<ThresholdSweepResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sweepableParams = useMemo(() => {
    const configParams = experiment.config.parameters;
    if (!configParams || typeof configParams !== "object") return [];
    if (paramSpecs.length === 0) return [];

    const result: SweepableParam[] = [];
    for (const spec of paramSpecs) {
      if (!isOptimizable(spec)) continue;
      if (isMultiPickParam(spec)) continue;
      if (!(spec.name in configParams)) continue;

      const currentValue = String(configParams[spec.name] ?? "");

      if (isNumericParam(spec)) {
        result.push({
          name: spec.name,
          displayName: spec.displayName || spec.name,
          kind: "numeric",
          currentValue,
          numericValue: Number(currentValue),
        });
      } else {
        const vocab = spec.vocabulary ? flattenVocab(spec.vocabulary) : [];
        if (vocab.length > 1) {
          result.push({
            name: spec.name,
            displayName: spec.displayName || spec.name,
            kind: "categorical",
            currentValue,
            vocab,
          });
        }
      }
    }
    return result;
  }, [paramSpecs, experiment.config.parameters]);

  const selectedParam = sweepableParams.find((p) => p.name === paramName) ?? null;
  const sweepType = selectedParam?.kind ?? "numeric";

  const vocabDisplayMap = useMemo(() => {
    if (!selectedParam?.vocab) return new Map<string, string>();
    return new Map(selectedParam.vocab.map((e) => [e.value, e.display]));
  }, [selectedParam]);

  const formatValue = useCallback(
    (v: number | string): string => {
      if (sweepType === "categorical") {
        return vocabDisplayMap.get(String(v)) ?? String(v);
      }
      return typeof v === "number" ? fmtNum(v) : v;
    },
    [sweepType, vocabDisplayMap],
  );

  const handleParamChange = useCallback(
    (name: string) => {
      setParamName(name);
      setFinalResult(null);
      setLivePoints([]);
      setError(null);

      const param = sweepableParams.find((p) => p.name === name);
      if (!param) return;

      if (param.kind === "numeric" && param.numericValue != null) {
        const cv = param.numericValue;
        setMinVal(String(Math.max(0, cv * 0.2)));
        setMaxVal(String(cv * 3));
      }

      if (param.kind === "categorical" && param.vocab) {
        setSelectedValues(new Set(param.vocab.map((e) => e.value)));
      }
    },
    [sweepableParams],
  );

  const handleRun = useCallback(async () => {
    if (!paramName || !selectedParam) return;

    let request: SweepRequest;
    if (selectedParam.kind === "numeric") {
      const mn = parseFloat(minVal);
      const mx = parseFloat(maxVal);
      const st = parseInt(steps);
      if (isNaN(mn) || isNaN(mx) || mn >= mx || isNaN(st)) return;
      request = {
        sweepType: "numeric",
        parameterName: paramName,
        minValue: mn,
        maxValue: mx,
        steps: Math.max(3, Math.min(50, st)),
      };
    } else {
      const values = Array.from(selectedValues);
      if (values.length < 2) return;
      request = {
        sweepType: "categorical",
        parameterName: paramName,
        values,
      };
    }

    setLivePoints([]);
    setCompletedCount(0);
    setTotalCount(0);
    setFinalResult(null);
    setError(null);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamThresholdSweep(
        experiment.id,
        request,
        {
          onPoint: (progress) => {
            setLivePoints((prev) => {
              const next = [...prev, progress.point];
              if (selectedParam.kind === "numeric") {
                next.sort((a, b) => Number(a.value) - Number(b.value));
              }
              return next;
            });
            setCompletedCount(progress.completedCount);
            setTotalCount(progress.totalCount);
          },
          onComplete: (result) => {
            setFinalResult(result);
          },
          onError: (err) => {
            setError(err.message);
          },
        },
        controller.signal,
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }, [experiment.id, paramName, selectedParam, minVal, maxVal, steps, selectedValues]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const displayPoints = finalResult?.points ?? livePoints;
  const validPoints = displayPoints.filter((p) => p.metrics != null);
  const failedPoints = displayPoints.filter((p) => p.metrics == null);
  const activeSweepType = finalResult?.sweepType ?? sweepType;

  if (specsLoading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading parameter specifications...
      </div>
    );
  }

  if (sweepableParams.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 px-5 py-8 text-center text-sm text-muted-foreground">
        No sweepable parameters detected in this experiment&apos;s configuration.
      </div>
    );
  }

  const canRun =
    selectedParam &&
    (selectedParam.kind === "numeric"
      ? paramName && minVal && maxVal
      : selectedValues.size >= 2);

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Sweep a parameter across a range (numeric) or set of values (categorical) to
        visualize the sensitivity/specificity trade-off.
      </p>

      {/* Parameter selector */}
      <div>
        <label className="mb-1 block text-xs font-medium text-muted-foreground">
          Parameter
        </label>
        <select
          value={paramName}
          onChange={(e) => handleParamChange(e.target.value)}
          className="h-8 w-full max-w-sm rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">Select...</option>
          <optgroup label="Numeric">
            {sweepableParams
              .filter((p) => p.kind === "numeric")
              .map((p) => (
                <option key={p.name} value={p.name}>
                  {p.displayName} (current: {p.currentValue})
                </option>
              ))}
          </optgroup>
          <optgroup label="Categorical">
            {sweepableParams
              .filter((p) => p.kind === "categorical")
              .map((p) => (
                <option key={p.name} value={p.name}>
                  {p.displayName} (current: {formatValue(p.currentValue)})
                </option>
              ))}
          </optgroup>
        </select>
      </div>

      {/* Numeric config */}
      {selectedParam?.kind === "numeric" && (
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Min
            </label>
            <input
              type="number"
              value={minVal}
              onChange={(e) => setMinVal(e.target.value)}
              className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Max
            </label>
            <input
              type="number"
              value={maxVal}
              onChange={(e) => setMaxVal(e.target.value)}
              className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Steps
            </label>
            <input
              type="number"
              min={3}
              max={50}
              value={steps}
              onChange={(e) => setSteps(e.target.value)}
              className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
      )}

      {/* Categorical config */}
      {selectedParam?.kind === "categorical" && selectedParam.vocab && (
        <CategoricalPicker
          vocab={selectedParam.vocab}
          selected={selectedValues}
          onChange={setSelectedValues}
        />
      )}

      {/* Run / Cancel */}
      <div className="flex items-center gap-2">
        {loading ? (
          <Button size="sm" variant="destructive" onClick={handleCancel}>
            <Square className="h-3.5 w-3.5" />
            Cancel
          </Button>
        ) : (
          <Button size="sm" onClick={handleRun} disabled={!canRun}>
            <Play className="h-3.5 w-3.5" />
            Run Sweep
          </Button>
        )}

        {loading && totalCount > 0 && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>
              {completedCount} / {totalCount} points
            </span>
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-300"
                style={{ width: `${(completedCount / totalCount) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {validPoints.length >= 2 && (
        <SweepChart
          points={validPoints}
          parameter={finalResult?.parameter ?? paramName}
          sweepType={activeSweepType}
          formatValue={formatValue}
          isStreaming={loading}
        />
      )}

      {validPoints.length >= 2 && !loading && finalResult && (
        <SweepSummary
          points={validPoints}
          parameter={finalResult.parameter}
          sweepType={activeSweepType}
          formatValue={formatValue}
          currentValue={selectedParam?.currentValue}
          failedCount={failedPoints.length}
        />
      )}

      {validPoints.length > 0 && (
        <SweepTable
          points={validPoints}
          parameter={finalResult?.parameter ?? paramName}
          formatValue={formatValue}
        />
      )}
    </div>
  );
}
