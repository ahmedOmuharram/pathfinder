import type { Message, OptimizationProgressData } from "@pathfinder/shared";

type AssistantPartTag = "thought" | "response" | "sources" | "optimization";

interface AssistantPart {
  tag: AssistantPartTag;
  key: string;
}

export function buildAssistantParts(
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
