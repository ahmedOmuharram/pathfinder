import { useState, useCallback } from "react";
import { Combine, RefreshCw, Plus, Minus, Loader2, Check } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { refineExperiment, reEvaluateExperiment } from "../../api";
import { useExperimentStore } from "../../store";
import { Section } from "./Section";

type CombineAction = "INTERSECT" | "UNION" | "MINUS";

interface ParameterRow {
  key: string;
  value: string;
}

interface Feedback {
  type: "success" | "error";
  message: string;
}

interface RefinePanelProps {
  experimentId: string;
  siteId: string;
}

const COMBINE_ACTIONS: { value: CombineAction; label: string }[] = [
  { value: "INTERSECT", label: "Intersect" },
  { value: "UNION", label: "Union" },
  { value: "MINUS", label: "Minus" },
];

export function RefinePanel({ experimentId }: RefinePanelProps) {
  const updateStore = useCallback(
    (
      exp: NonNullable<
        ReturnType<typeof useExperimentStore.getState>["currentExperiment"]
      >,
    ) => {
      useExperimentStore.setState({ currentExperiment: exp });
    },
    [],
  );

  const [combineAction, setCombineAction] = useState<CombineAction>("INTERSECT");
  const [searchName, setSearchName] = useState("");
  const [parameters, setParameters] = useState<ParameterRow[]>([
    { key: "", value: "" },
  ]);
  const [combineLoading, setCombineLoading] = useState(false);
  const [combineFeedback, setCombineFeedback] = useState<Feedback | null>(null);

  const [reEvalLoading, setReEvalLoading] = useState(false);
  const [reEvalFeedback, setReEvalFeedback] = useState<Feedback | null>(null);

  const addParameterRow = () => {
    setParameters((prev) => [...prev, { key: "", value: "" }]);
  };

  const removeParameterRow = (index: number) => {
    setParameters((prev) =>
      prev.length <= 1 ? prev : prev.filter((_, i) => i !== index),
    );
  };

  const updateParameter = (index: number, field: "key" | "value", val: string) => {
    setParameters((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: val } : row)),
    );
  };

  const handleCombine = async () => {
    setCombineLoading(true);
    setCombineFeedback(null);

    const paramMap: Record<string, string> = {};
    for (const row of parameters) {
      const trimmedKey = row.key.trim();
      if (trimmedKey) paramMap[trimmedKey] = row.value;
    }

    try {
      const result = await refineExperiment(experimentId, "combine", {
        combineAction,
        searchName: searchName.trim(),
        parameters: paramMap,
      });

      if (result.success) {
        setCombineFeedback({
          type: "success",
          message: result.newStepId
            ? `Combined successfully — new step #${result.newStepId}`
            : "Combine applied successfully",
        });
        setSearchName("");
        setParameters([{ key: "", value: "" }]);
      } else {
        setCombineFeedback({
          type: "error",
          message: "Combine failed — no changes applied",
        });
      }
    } catch (err) {
      setCombineFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "An unexpected error occurred",
      });
    } finally {
      setCombineLoading(false);
    }
  };

  const handleReEvaluate = async () => {
    setReEvalLoading(true);
    setReEvalFeedback(null);

    try {
      const updatedExperiment = await reEvaluateExperiment(experimentId);
      updateStore(updatedExperiment);
      setReEvalFeedback({
        type: "success",
        message: "Controls re-evaluated successfully",
      });
    } catch (err) {
      setReEvalFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Re-evaluation failed",
      });
    } finally {
      setReEvalLoading(false);
    }
  };

  const canCombine = searchName.trim().length > 0;

  return (
    <div className="space-y-6">
      {/* Combine Section */}
      <Section title="Combine with Another Search">
        <div className="space-y-4 rounded-lg border border-border bg-card p-5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Combine className="h-4 w-4" />
            <span>Add a boolean combine step to the current strategy</span>
          </div>

          {/* Action selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Action</label>
            <div className="flex gap-2">
              {COMBINE_ACTIONS.map((action) => (
                <button
                  key={action.value}
                  type="button"
                  onClick={() => setCombineAction(action.value)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium transition ${
                    combineAction === action.value
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-background text-muted-foreground hover:border-primary/40 hover:text-foreground"
                  }`}
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>

          {/* Search name */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Search Name
            </label>
            <input
              type="text"
              value={searchName}
              onChange={(e) => setSearchName(e.target.value)}
              placeholder="e.g. GenesByTaxon"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          {/* Parameters */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-muted-foreground">
                Parameters
              </label>
              <button
                type="button"
                onClick={addParameterRow}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground transition hover:text-foreground"
              >
                <Plus className="h-3 w-3" />
                Add row
              </button>
            </div>

            <div className="space-y-2">
              {parameters.map((row, index) => (
                <div key={index} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={row.key}
                    onChange={(e) => updateParameter(index, "key", e.target.value)}
                    placeholder="key"
                    className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <span className="text-xs text-muted-foreground">=</span>
                  <input
                    type="text"
                    value={row.value}
                    onChange={(e) => updateParameter(index, "value", e.target.value)}
                    placeholder="value"
                    className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <button
                    type="button"
                    onClick={() => removeParameterRow(index)}
                    disabled={parameters.length <= 1}
                    className="rounded p-1 text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive disabled:opacity-30"
                  >
                    <Minus className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Apply button + feedback */}
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              disabled={!canCombine || combineLoading}
              loading={combineLoading}
              onClick={handleCombine}
            >
              <Combine className="h-3.5 w-3.5" />
              Apply Combine
            </Button>
            <Badge variant="secondary" className="text-xs">
              {combineAction}
            </Badge>
            <InlineFeedback feedback={combineFeedback} />
          </div>
        </div>
      </Section>

      {/* Re-evaluate Section */}
      <Section title="Re-evaluate Controls">
        <div className="space-y-4 rounded-lg border border-border bg-card p-5">
          <p className="text-xs text-muted-foreground">
            Re-run the experiment&apos;s control evaluation against the current strategy
            results. This will recompute sensitivity, specificity, and other metrics.
          </p>

          <div className="flex items-center gap-3">
            <Button
              size="sm"
              variant="outline"
              disabled={reEvalLoading}
              loading={reEvalLoading}
              onClick={handleReEvaluate}
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${reEvalLoading ? "animate-spin" : ""}`}
              />
              Re-evaluate Controls
            </Button>
            <InlineFeedback feedback={reEvalFeedback} />
          </div>
        </div>
      </Section>
    </div>
  );
}

function InlineFeedback({ feedback }: { feedback: Feedback | null }) {
  if (!feedback) return null;

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium ${
        feedback.type === "success" ? "text-success" : "text-destructive"
      }`}
    >
      {feedback.type === "success" ? (
        <Check className="h-3.5 w-3.5" />
      ) : (
        <Loader2 className="h-3.5 w-3.5" />
      )}
      {feedback.message}
    </span>
  );
}
