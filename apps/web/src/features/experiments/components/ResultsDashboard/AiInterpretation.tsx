import { useState, useRef, useCallback } from "react";
import type { Experiment } from "@pathfinder/shared";
import { streamAiAssist } from "../../api";
import { ChatMarkdown } from "@/features/chat/components/ChatMarkdown";
import { Sparkles, Loader2 } from "lucide-react";
import { Section } from "./Section";

interface AiInterpretationProps {
  experiment: Experiment;
  siteId: string;
}

export function AiInterpretation({ experiment, siteId }: AiInterpretationProps) {
  const [response, setResponse] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const interpret = useCallback(() => {
    if (streaming) return;

    abortRef.current?.abort();
    setStreaming(true);
    setResponse("");
    setHasRun(true);

    const m = experiment.metrics;
    const cm = m?.confusionMatrix;
    const enrichSummary = experiment.enrichmentResults
      .map((er) => {
        const top = er.terms
          .filter((t) => t.pValue < 0.05)
          .slice(0, 5)
          .map(
            (t) =>
              `${t.termName} (p=${t.pValue.toExponential(2)}, fold=${t.foldEnrichment.toFixed(1)})`,
          )
          .join("; ");
        return `${er.analysisType}: ${top || "no significant terms"}`;
      })
      .join("\n");

    const context: Record<string, unknown> = {
      searchName: experiment.config.searchName,
      recordType: experiment.config.recordType,
      parameters:
        experiment.config.parameterDisplayValues ?? experiment.config.parameters,
      positiveControls: experiment.config.positiveControls.slice(0, 20),
      negativeControls: experiment.config.negativeControls.slice(0, 20),
    };

    if (m) {
      context.metrics = {
        sensitivity: m.sensitivity,
        specificity: m.specificity,
        precision: m.precision,
        f1Score: m.f1Score,
        mcc: m.mcc,
        balancedAccuracy: m.balancedAccuracy,
        totalResults: m.totalResults,
      };
    }
    if (cm) {
      context.confusionMatrix = {
        TP: cm.truePositives,
        FP: cm.falsePositives,
        FN: cm.falseNegatives,
        TN: cm.trueNegatives,
      };
    }
    if (enrichSummary) {
      context.enrichmentSummary = enrichSummary;
    }
    if (experiment.crossValidation) {
      context.crossValidation = {
        overfittingLevel: experiment.crossValidation.overfittingLevel,
        overfittingScore: experiment.crossValidation.overfittingScore,
        meanF1: experiment.crossValidation.meanMetrics.f1Score,
      };
    }

    abortRef.current = streamAiAssist(
      {
        siteId,
        step: "results",
        message:
          "Please interpret these experiment results. Provide a clear scientific assessment, " +
          "explain what the metrics mean for this specific search, highlight key enrichment findings, " +
          "and suggest concrete next steps.",
        context,
        history: [],
      },
      {
        onDelta: (delta) => setResponse((prev) => prev + delta),
        onComplete: () => setStreaming(false),
        onError: () => setStreaming(false),
      },
    );
  }, [experiment, siteId, streaming]);

  return (
    <Section title="AI Interpretation">
      <div className="rounded-lg border border-slate-200 bg-white">
        {!hasRun ? (
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="text-[13px] text-slate-600">
                Get an AI-generated analysis of your results with actionable next steps.
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">
                The AI will interpret metrics, enrichment findings, and suggest
                improvements.
              </p>
            </div>
            <button
              type="button"
              onClick={interpret}
              className="flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-600 px-4 py-2 text-xs font-medium text-white transition hover:bg-indigo-700"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Interpret Results
            </button>
          </div>
        ) : (
          <div className="px-5 py-4">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                <span className="text-xs font-semibold text-slate-700">
                  AI Analysis
                </span>
              </div>
              {!streaming && (
                <button
                  type="button"
                  onClick={interpret}
                  className="text-[10px] text-slate-400 transition hover:text-slate-600"
                >
                  Re-analyze
                </button>
              )}
            </div>
            {response ? (
              <ChatMarkdown
                content={response}
                className="text-[12px] leading-relaxed text-slate-700 [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_p]:break-words [&_h1]:text-sm [&_h2]:text-[13px] [&_h3]:text-[12px]"
              />
            ) : (
              <div className="flex items-center gap-1.5 py-4 text-[11px] text-slate-400">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Analyzing experiment results...
              </div>
            )}
          </div>
        )}
      </div>
    </Section>
  );
}
