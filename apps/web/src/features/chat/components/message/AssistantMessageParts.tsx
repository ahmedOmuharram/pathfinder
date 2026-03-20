import type {
  Message,
  OptimizationProgressData,
  PlanningArtifact,
  ToolCall,
  Strategy,
} from "@pathfinder/shared";
import { ChatThinkingDetails } from "@/features/chat/components/thinking/ChatThinkingDetails";
import { OptimizationProgressPanel } from "@/features/chat/components/optimization/OptimizationProgressPanel";
import { ThinkingPanel } from "@/features/chat/components/thinking/ThinkingPanel";
import { extractDelegateSummaries } from "@/features/chat/utils/extractDelegateSummaries";
import { SourcesPart } from "./SourcesPart";
import { ResponsePart } from "./ResponsePart";
import { buildAssistantParts } from "./useAssistantParts";

interface ThinkingState {
  activeToolCalls: ToolCall[];
  lastToolCalls: ToolCall[];
  subKaniCalls: Record<string, ToolCall[]>;
  subKaniStatus: Record<string, string>;
  subKaniModels?: Record<string, string>;
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
  undoSnapshot?: Strategy;
  onUndoSnapshot: (snapshot: Strategy) => void;
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
    <div className="flex flex-col gap-1">
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
                {...(thinking.subKaniModels != null
                  ? { subKaniModels: thinking.subKaniModels }
                  : {})}
                {...(thinking.reasoning != null
                  ? { reasoning: thinking.reasoning }
                  : {})}
                title="Thinking"
              />
            ) : (
              <ChatThinkingDetails
                key={part.key}
                {...(message.toolCalls != null ? { toolCalls: message.toolCalls } : {})}
                delegateSummaries={delegateSummary.summaries}
                delegateRejected={delegateSummary.rejected}
                {...(message.subKaniActivity != null
                  ? { subKaniActivity: message.subKaniActivity }
                  : {})}
                {...(message.reasoning != null ? { reasoning: message.reasoning } : {})}
                title="Thought"
              />
            );
          case "response":
            return (
              <ResponsePart
                key={part.key}
                message={message}
                {...(onApplyPlanningArtifact != null
                  ? { onApplyPlanningArtifact }
                  : {})}
              />
            );
          case "sources":
            return (
              <SourcesPart
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
                {...(isLive && onCancelOptimization != null
                  ? { onCancel: onCancelOptimization }
                  : {})}
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

function UndoButton({ onClick }: { onClick: () => void }) {
  return (
    <div className="flex justify-start">
      <button
        type="button"
        onClick={onClick}
        className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-input hover:bg-accent"
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
