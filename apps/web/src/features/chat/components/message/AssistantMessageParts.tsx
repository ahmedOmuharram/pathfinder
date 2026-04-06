import type {
  AssistantMessage,
  OptimizationProgressData,
  PlanningArtifact,
  ToolCall,
  Strategy,
} from "@pathfinder/shared";
import { ChatThinkingDetails } from "@/features/chat/components/thinking/ChatThinkingDetails";
import { OptimizationProgressPanel } from "@/features/chat/components/optimization/OptimizationProgressPanel";
import { ThinkingPanel } from "@/features/chat/components/thinking/ThinkingPanel";
import { PlanThinkingBlock } from "@/features/chat/components/plan/PlanThinkingBlock";
import { extractDelegateSummaries } from "@/features/chat/utils/extractDelegateSummaries";
import { usePlanStore } from "@/state/usePlanStore";
import { SourcesPart } from "./SourcesPart";
import { ResponsePart } from "./ResponsePart";
import { buildAssistantParts } from "./useAssistantParts";

interface ThinkingState {
  activeToolCalls: ToolCall[];
  lastToolCalls: ToolCall[];
  reasoning?: string | null;
}

interface AssistantMessagePartsProps {
  index: number;
  message: AssistantMessage;
  messageKey: string;
  isLive: boolean;
  thinking: ThinkingState;
  optimizationProgress?: OptimizationProgressData | null;
  onCancelOptimization?: () => void;
  isApplyingArtifact?: boolean;
  onApplyPlanningArtifact?: (artifact: PlanningArtifact) => void;
  onSendMessage?: (text: string, metadata?: Record<string, unknown>) => void;
  expandedSources: Record<string, boolean>;
  setExpandedSources: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  showCitationTags: boolean;
  setShowCitationTags: React.Dispatch<React.SetStateAction<boolean>>;
  undoSnapshot?: Strategy;
}

export function AssistantMessageParts({
  index,
  message,
  messageKey,
  isLive,
  thinking,
  optimizationProgress,
  onCancelOptimization,
  isApplyingArtifact = false,
  onApplyPlanningArtifact,
  expandedSources,
  setExpandedSources,
  showCitationTags,
  setShowCitationTags,
}: AssistantMessagePartsProps) {
  const parts = buildAssistantParts(index, message, isLive, optimizationProgress);
  const delegateSummary = message.toolCalls
    ? extractDelegateSummaries(message.toolCalls)
    : { summaries: [], rejected: [] };

  const planThoughts = usePlanStore((s) => s.planThoughts);

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
                {...(message.reasoning != null ? { reasoning: message.reasoning } : {})}
                title="Thought"
              />
            );
          case "response":
            return (
              <ResponsePart
                key={part.key}
                message={message}
                isApplyingArtifact={isApplyingArtifact}
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

      {/* Plan thinking — persists after streaming ends */}
      {planThoughts.length > 0 && (
        <PlanThinkingBlock thoughts={planThoughts} isLive={isLive} />
      )}

      {/* Plan card now renders in the right-side PlanPanel (page.tsx), not inline */}
    </div>
  );
}
