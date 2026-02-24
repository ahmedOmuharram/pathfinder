import { useState, useEffect, useCallback } from "react";
import { FlaskConical, Play, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { getExperimentAnalysisTypes, runExperimentAnalysis } from "../../api";

interface StepAnalysisPanelProps {
  experimentId: string;
}

interface AnalysisType {
  name: string;
  displayName?: string;
  description?: string;
  parameters?: { name: string; displayName?: string; defaultValue?: string }[];
}

function normalizeTypes(raw: Record<string, unknown>[]): AnalysisType[] {
  return raw.map((t) => ({
    name: String(t.name ?? ""),
    displayName: t.displayName != null ? String(t.displayName) : undefined,
    description: t.description != null ? String(t.description) : undefined,
    parameters: Array.isArray(t.parameters)
      ? (t.parameters as Record<string, unknown>[]).map((p) => ({
          name: String(p.name ?? ""),
          displayName: p.displayName != null ? String(p.displayName) : undefined,
          defaultValue: p.defaultValue != null ? String(p.defaultValue) : undefined,
        }))
      : undefined,
  }));
}

function AnalysisResultView({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Analysis completed with no output data.
      </p>
    );
  }

  const isSimpleTable = entries.every(([, v]) => typeof v !== "object" || v === null);

  if (isSimpleTable) {
    return (
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2 font-medium">Key</th>
              <th className="px-4 py-2 font-medium">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td className="px-4 py-1.5 font-medium text-muted-foreground">{key}</td>
                <td className="px-4 py-1.5 font-mono tabular-nums text-foreground">
                  {String(value ?? "—")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <pre className="max-h-64 overflow-auto rounded-lg border border-border bg-muted/30 p-3 text-xs leading-relaxed text-foreground">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

export function StepAnalysisPanel({ experimentId }: StepAnalysisPanelProps) {
  const [analysisTypes, setAnalysisTypes] = useState<AnalysisType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<AnalysisType | null>(null);
  const [paramValues, setParamValues] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getExperimentAnalysisTypes(experimentId)
      .then(({ analysisTypes: types }) => {
        if (!cancelled) setAnalysisTypes(normalizeTypes(types));
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [experimentId]);

  const selectType = useCallback((type: AnalysisType) => {
    setSelectedType(type);
    setResults(null);
    setRunError(null);
    const defaults: Record<string, string> = {};
    type.parameters?.forEach((p) => {
      defaults[p.name] = p.defaultValue ?? "";
    });
    setParamValues(defaults);
  }, []);

  const handleRun = useCallback(async () => {
    if (!selectedType) return;
    setRunning(true);
    setRunError(null);
    setResults(null);

    try {
      const result = await runExperimentAnalysis(
        experimentId,
        selectedType.name,
        paramValues,
      );
      setResults(result);
    } catch (err) {
      setRunError(String(err));
    } finally {
      setRunning(false);
    }
  }, [experimentId, selectedType, paramValues]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading analysis types…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-destructive">
        <FlaskConical className="h-4 w-4" />
        {error}
      </div>
    );
  }

  if (analysisTypes.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center text-sm text-muted-foreground">
        <FlaskConical className="h-5 w-5" />
        No step analyses available for this experiment.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {analysisTypes.map((type) => {
          const active = selectedType?.name === type.name;
          return (
            <button
              key={type.name}
              type="button"
              onClick={() => selectType(type)}
              className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition ${
                active
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-card text-foreground hover:border-primary/40 hover:bg-accent"
              }`}
            >
              <FlaskConical className="h-3.5 w-3.5" />
              {type.displayName ?? type.name}
            </button>
          );
        })}
      </div>

      {selectedType && (
        <div className="space-y-3 rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-foreground">
              {selectedType.displayName ?? selectedType.name}
            </h3>
            <Badge variant="secondary">{selectedType.name}</Badge>
          </div>

          {selectedType.description && (
            <p className="text-xs text-muted-foreground">{selectedType.description}</p>
          )}

          {selectedType.parameters && selectedType.parameters.length > 0 && (
            <div className="space-y-2">
              {selectedType.parameters.map((param) => (
                <div key={param.name} className="flex items-center gap-3">
                  <label
                    htmlFor={`param-${param.name}`}
                    className="w-36 shrink-0 text-xs font-medium text-muted-foreground"
                  >
                    {param.displayName ?? param.name}
                  </label>
                  <input
                    id={`param-${param.name}`}
                    type="text"
                    value={paramValues[param.name] ?? ""}
                    onChange={(e) =>
                      setParamValues((prev) => ({
                        ...prev,
                        [param.name]: e.target.value,
                      }))
                    }
                    className="h-8 flex-1 rounded-md border border-input bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder={param.defaultValue ?? ""}
                  />
                </div>
              ))}
            </div>
          )}

          <Button size="sm" onClick={handleRun} loading={running} disabled={running}>
            <Play className="h-3.5 w-3.5" />
            Run Analysis
          </Button>

          {runError && <p className="text-xs text-destructive">{runError}</p>}

          {results && <AnalysisResultView data={results} />}
        </div>
      )}
    </div>
  );
}
