import { ChevronDown, ChevronUp } from "lucide-react";
import type {
  Message,
  OptimizationProgressData,
  PlanningArtifact,
  ToolCall,
} from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/types/strategy";
import { ChatMarkdown } from "@/features/chat/components/ChatMarkdown";
import { ChatThinkingDetails } from "@/features/chat/components/ChatThinkingDetails";
import { OptimizationProgressPanel } from "@/features/chat/components/OptimizationProgressPanel";
import { ThinkingPanel } from "@/features/chat/components/ThinkingPanel";
import { extractDelegateSummaries } from "@/features/chat/utils/extractDelegateSummaries";

type AssistantPartTag = "thought" | "response" | "sources" | "optimization";

interface AssistantPart {
  tag: AssistantPartTag;
  key: string;
}

interface ThinkingState {
  activeToolCalls: ToolCall[];
  lastToolCalls: ToolCall[];
  subKaniCalls: Record<string, ToolCall[]>;
  subKaniStatus: Record<string, string>;
  reasoning?: string | null;
}

interface AssistantMessagePartsProps {
  index: number;
  message: Message;
  messageKey: string;
  isLive: boolean;
  thinking: ThinkingState;
  optimizationProgress?: OptimizationProgressData | null;
  onCancelOptimization?: () => void;
  onApplyPlanningArtifact?: (artifact: PlanningArtifact) => void;
  expandedSources: Record<string, boolean>;
  setExpandedSources: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  showCitationTags: boolean;
  setShowCitationTags: React.Dispatch<React.SetStateAction<boolean>>;
  undoSnapshot?: StrategyWithMeta;
  onUndoSnapshot: (snapshot: StrategyWithMeta) => void;
}

function buildAssistantParts(
  index: number,
  message: Message,
  isLiveStreaming: boolean,
  liveOptimization: OptimizationProgressData | null | undefined,
): AssistantPart[] {
  const parts: AssistantPart[] = [];

  if (isLiveStreaming) {
    parts.push({ tag: "thought", key: `${index}-thought` });
  } else {
    const hasToolCalls = (message.toolCalls?.length ?? 0) > 0;
    const hasSubKani = Object.keys(message.subKaniActivity?.calls ?? {}).length > 0;
    const hasReasoning = Boolean(message.reasoning?.trim());
    if (hasToolCalls || hasSubKani || hasReasoning) {
      parts.push({ tag: "thought", key: `${index}-thought` });
    }
  }

  parts.push({ tag: "response", key: `${index}-response` });

  if (Array.isArray(message.citations) && message.citations.length > 0) {
    parts.push({ tag: "sources", key: `${index}-sources` });
  }

  if (liveOptimization || message.optimizationProgress) {
    parts.push({ tag: "optimization", key: `${index}-optimization` });
  }

  return parts;
}

export function AssistantMessageParts({
  index,
  message,
  messageKey,
  isLive,
  thinking,
  optimizationProgress,
  onCancelOptimization,
  onApplyPlanningArtifact,
  expandedSources,
  setExpandedSources,
  showCitationTags,
  setShowCitationTags,
  undoSnapshot,
  onUndoSnapshot,
}: AssistantMessagePartsProps) {
  const parts = buildAssistantParts(index, message, isLive, optimizationProgress);
  const delegateSummary = message.toolCalls
    ? extractDelegateSummaries(message.toolCalls)
    : { summaries: [], rejected: [] };

  return (
    <div className="flex max-w-[85%] flex-col gap-1">
      {parts.map((part) => {
        switch (part.tag) {
          case "thought":
            return isLive ? (
              <ThinkingPanel
                key={part.key}
                isStreaming
                activeToolCalls={thinking.activeToolCalls}
                lastToolCalls={thinking.lastToolCalls}
                subKaniCalls={thinking.subKaniCalls}
                subKaniStatus={thinking.subKaniStatus}
                reasoning={thinking.reasoning}
                title="Thinking"
              />
            ) : (
              <ChatThinkingDetails
                key={part.key}
                toolCalls={message.toolCalls}
                delegateSummaries={delegateSummary.summaries}
                delegateRejected={delegateSummary.rejected}
                subKaniActivity={message.subKaniActivity}
                reasoning={message.reasoning}
                title="Thought"
              />
            );
          case "response":
            return (
              <div
                key={part.key}
                className="rounded-lg px-3 py-2 border border-slate-200 bg-slate-50 text-slate-700"
              >
                <ChatMarkdown
                  content={message.content}
                  citations={message.citations}
                  tone="default"
                />
                {Array.isArray(message.planningArtifacts) &&
                  message.planningArtifacts.length > 0 && (
                    <div className="mt-2 rounded-md border border-slate-200 bg-white px-2 py-2 text-[12px] text-slate-700">
                      <div className="mb-1 font-medium text-slate-900">
                        Saved planning artifacts
                      </div>
                      <ul className="list-disc space-y-1 pl-4">
                        {message.planningArtifacts.map((a) => (
                          <li key={a.id}>
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-medium">{a.title}</span>
                              {a.proposedStrategyPlan && onApplyPlanningArtifact ? (
                                <button
                                  type="button"
                                  onClick={() => onApplyPlanningArtifact(a)}
                                  className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
                                >
                                  Apply to strategy
                                </button>
                              ) : null}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
              </div>
            );
          case "sources":
            return (
              <SourcesSection
                key={part.key}
                messageKey={messageKey}
                citations={message.citations!}
                expandedSources={expandedSources}
                setExpandedSources={setExpandedSources}
                showCitationTags={showCitationTags}
                setShowCitationTags={setShowCitationTags}
              />
            );
          case "optimization": {
            const data = (optimizationProgress ?? message.optimizationProgress)!;
            return (
              <OptimizationProgressPanel
                key={part.key}
                data={data}
                onCancel={isLive ? onCancelOptimization : undefined}
              />
            );
          }
          default:
            return null;
        }
      })}

      {undoSnapshot && <UndoButton onClick={() => onUndoSnapshot(undoSnapshot)} />}
    </div>
  );
}

function SourcesSection({
  messageKey,
  citations,
  expandedSources,
  setExpandedSources,
  showCitationTags,
  setShowCitationTags,
}: {
  messageKey: string;
  citations: NonNullable<Message["citations"]>;
  expandedSources: Record<string, boolean>;
  setExpandedSources: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  showCitationTags: boolean;
  setShowCitationTags: React.Dispatch<React.SetStateAction<boolean>>;
}) {
  const total = citations.length;
  const expanded = Boolean(expandedSources[messageKey]);

  return (
    <div className="rounded-md border border-slate-200 bg-white px-2 py-2 text-[12px] text-slate-700">
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="font-medium text-slate-900">Sources</div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={`rounded-md border px-2 py-1 text-[11px] transition-colors ${
              showCitationTags
                ? "border-slate-300 bg-slate-50 text-slate-900"
                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            }`}
            onClick={() => setShowCitationTags((v) => !v)}
            aria-pressed={showCitationTags}
            title="Toggle citation tags"
          >
            {showCitationTags ? "Hide citation tags" : "Show citation tags"}
          </button>
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-white p-1 text-slate-700 hover:bg-slate-50"
            onClick={() =>
              setExpandedSources((prev) => ({
                ...prev,
                [messageKey]: !expanded,
              }))
            }
            aria-label={expanded ? "Collapse sources" : "Expand sources"}
            title={expanded ? "Collapse sources" : "Expand sources"}
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
            ) : (
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {!expanded ? (
        <div className="text-[11px] text-slate-500">
          {total} source{total === 1 ? "" : "s"}
        </div>
      ) : (
        <ol className="list-decimal space-y-1 pl-4">
          {citations.map((c, i) => (
            <li key={c.id} id={`cite-${i + 1}`}>
              {showCitationTags && c.tag ? (
                <span className="mr-2 font-mono text-[11px] text-slate-500">
                  [{c.tag}]{" "}
                </span>
              ) : null}
              {Array.isArray(c.authors) && c.authors.length > 0 ? (
                <span className="text-slate-600">
                  {`${c.authors.filter(Boolean).join(", ")} `}
                </span>
              ) : null}
              {c.url ? (
                <a
                  href={c.url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline decoration-slate-300 underline-offset-2 hover:decoration-slate-500"
                >
                  {c.title}
                </a>
              ) : (
                <span>{c.title}</span>
              )}
              {c.year ? <span className="text-slate-500"> ({c.year})</span> : null}
              {c.doi ? <span className="text-slate-500"> · DOI: {c.doi}</span> : null}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function UndoButton({ onClick }: { onClick: () => void }) {
  return (
    <div className="flex justify-start">
      <button
        type="button"
        onClick={onClick}
        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
        title="Undo model changes"
        aria-label="Undo model changes"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          className="h-3.5 w-3.5"
        >
          <path d="M9 14L4 9l5-5" />
          <path d="M20 20v-5a7 7 0 0 0-7-7H4" />
        </svg>
        Undo
      </button>
    </div>
  );
}
