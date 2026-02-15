import { useState } from "react";
import type { Message, ToolCall, PlanningArtifact } from "@pathfinder/shared";
import type { ChatMode } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/types/strategy";
import { decodeNodeSelection } from "@/features/chat/node_selection";
import { extractDelegateSummaries } from "@/features/chat/utils/extractDelegateSummaries";
import { ChatEmptyState } from "@/features/chat/components/ChatEmptyState";
import { NodeCard } from "@/features/chat/components/NodeCard";
import { ChatMarkdown } from "@/features/chat/components/ChatMarkdown";
import { ChatThinkingDetails } from "@/features/chat/components/ChatThinkingDetails";
import { ThinkingPanel } from "@/features/chat/components/ThinkingPanel";
import { ChevronDown, ChevronUp } from "lucide-react";

interface ChatMessageListProps {
  isCompact: boolean;
  siteId: string;
  displayName: string;
  firstName?: string;
  signedIn: boolean;
  mode?: ChatMode;
  isStreaming: boolean;
  messages: Message[];
  undoSnapshots: Record<number, StrategyWithMeta>;
  onSend: (content: string) => void;
  onUndoSnapshot: (snapshot: StrategyWithMeta) => void;
  onApplyPlanningArtifact?: (artifact: PlanningArtifact) => void;
  thinking: {
    activeToolCalls: ToolCall[];
    lastToolCalls: ToolCall[];
    subKaniCalls: Record<string, ToolCall[]>;
    subKaniStatus: Record<string, string>;
    reasoning?: string | null;
  };
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
}

export function ChatMessageList({
  isCompact,
  siteId,
  displayName,
  firstName,
  signedIn,
  mode = "execute",
  isStreaming,
  messages,
  undoSnapshots,
  onSend,
  onUndoSnapshot,
  onApplyPlanningArtifact,
  thinking,
  messagesEndRef,
}: ChatMessageListProps) {
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [showCitationTags, setShowCitationTags] = useState(false);

  const lastMessageRole =
    messages.length > 0 ? messages[messages.length - 1]?.role : null;
  const thinkingInsertIndex =
    mode === "plan"
      ? (() => {
          // Critical UX: when a *new* planning turn starts, we don't want to mutate/show
          // the thinking panel above the previous assistant response. Until the first
          // assistant tokens arrive (i.e., an assistant message exists at the end),
          // keep the thinking panel at the bottom.
          if (isStreaming && lastMessageRole !== "assistant") {
            return null;
          }
          for (let i = messages.length - 1; i >= 0; i -= 1) {
            if (messages[i]?.role === "assistant") return i;
          }
          return null;
        })()
      : null;

  return (
    <div className="relative flex-1 min-h-0">
      <div
        className={`chat-messages h-full min-h-0 space-y-3 overflow-y-auto ${
          isCompact ? "p-2" : "p-4"
        }`}
      >
        <ChatEmptyState
          isCompact={isCompact}
          siteId={siteId}
          displayName={displayName}
          firstName={firstName}
          signedIn={signedIn}
          onSend={onSend}
          isStreaming={isStreaming}
          hasMessages={messages.length > 0}
        />

        {messages.map((message, index) => {
          const decoded =
            message.role === "user"
              ? decodeNodeSelection(message.content)
              : { selection: null, message: message.content };
          const nodeData = decoded.selection;
          const hasText = decoded.message && decoded.message.length > 0;
          const delegateSummary =
            message.role === "assistant" && message.toolCalls
              ? extractDelegateSummaries(message.toolCalls)
              : { summaries: [], rejected: [] };
          const subKaniActivity =
            message.role === "assistant" ? message.subKaniActivity : undefined;
          const undoSnapshot = undoSnapshots[index];
          const nodeList = Array.isArray(nodeData?.nodes) ? nodeData.nodes : [];
          const nodeIds = Array.isArray(nodeData?.nodeIds) ? nodeData.nodeIds : [];
          const messageKey = `${index}-${message.timestamp}`;
          return (
            <div key={index} className="space-y-2">
              {mode === "plan" && thinkingInsertIndex === index ? (
                <ThinkingPanel
                  isStreaming={isStreaming}
                  activeToolCalls={thinking.activeToolCalls}
                  lastToolCalls={thinking.lastToolCalls}
                  subKaniCalls={thinking.subKaniCalls}
                  subKaniStatus={thinking.subKaniStatus}
                  reasoning={thinking.reasoning}
                  title="Thinking"
                />
              ) : null}

              <div
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                } animate-fade-in`}
              >
                {nodeData ? (
                  <div className="flex max-w-[85%] flex-col items-end gap-1">
                    <div className="flex w-full gap-2 overflow-x-auto pb-1">
                      {nodeList.map((node, nodeIndex) => (
                        <div
                          key={`${nodeIds[nodeIndex] || nodeIndex}`}
                          className="shrink-0 min-w-[220px]"
                        >
                          <NodeCard node={node} />
                        </div>
                      ))}
                    </div>
                    {hasText && (
                      <div className="rounded-lg bg-slate-900 px-3 py-2 text-white selection:bg-white selection:text-slate-900">
                        <ChatMarkdown content={decoded.message} tone="onDark" />
                      </div>
                    )}
                    {message.role === "assistant" && undoSnapshot && (
                      <div className="flex w-full justify-start">
                        <button
                          type="button"
                          onClick={() => onUndoSnapshot(undoSnapshot)}
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
                    )}
                  </div>
                ) : (
                  <div className="flex max-w-[85%] flex-col gap-1">
                    {message.role === "assistant" ? (
                      <ChatThinkingDetails
                        toolCalls={message.toolCalls}
                        delegateSummaries={delegateSummary.summaries}
                        delegateRejected={delegateSummary.rejected}
                        subKaniActivity={subKaniActivity}
                        title="Thought"
                      />
                    ) : null}
                    <div
                      className={`rounded-lg px-3 py-2 ${
                        message.role === "user"
                          ? "bg-slate-900 text-white selection:bg-white selection:text-slate-900"
                          : "border border-slate-200 bg-slate-50 text-slate-700"
                      }`}
                    >
                      <ChatMarkdown
                        content={message.content}
                        citations={
                          message.role === "assistant" ? message.citations : undefined
                        }
                        tone={message.role === "user" ? "onDark" : "default"}
                      />
                      {message.role === "assistant" &&
                        Array.isArray(message.planningArtifacts) &&
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
                                    {a.proposedStrategyPlan &&
                                    onApplyPlanningArtifact ? (
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
                      {message.role === "assistant" &&
                        Array.isArray(message.citations) &&
                        message.citations.length > 0 && (
                          <div className="mt-2 rounded-md border border-slate-200 bg-white px-2 py-2 text-[12px] text-slate-700">
                            {(() => {
                              const total = message.citations?.length || 0;
                              const expanded = Boolean(expandedSources[messageKey]);

                              return (
                                <>
                                  <div className="mb-1 flex items-center justify-between gap-2">
                                    <div className="font-medium text-slate-900">
                                      Sources
                                    </div>
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
                                        {showCitationTags
                                          ? "Hide citation tags"
                                          : "Show citation tags"}
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
                                        aria-label={
                                          expanded
                                            ? "Collapse sources"
                                            : "Expand sources"
                                        }
                                        title={
                                          expanded
                                            ? "Collapse sources"
                                            : "Expand sources"
                                        }
                                      >
                                        {expanded ? (
                                          <ChevronUp
                                            className="h-4 w-4"
                                            aria-hidden="true"
                                          />
                                        ) : (
                                          <ChevronDown
                                            className="h-4 w-4"
                                            aria-hidden="true"
                                          />
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
                                      {message.citations.map((c, i) => (
                                        <li key={c.id} id={`cite-${i + 1}`}>
                                          {showCitationTags && c.tag ? (
                                            <span className="mr-2 font-mono text-[11px] text-slate-500">
                                              [{c.tag}]{" "}
                                            </span>
                                          ) : null}
                                          {Array.isArray(c.authors) &&
                                          c.authors.length > 0 ? (
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
                                          {c.year ? (
                                            <span className="text-slate-500">
                                              {" "}
                                              ({c.year})
                                            </span>
                                          ) : null}
                                          {c.doi ? (
                                            <span className="text-slate-500">
                                              {" "}
                                              · DOI: {c.doi}
                                            </span>
                                          ) : null}
                                        </li>
                                      ))}
                                    </ol>
                                  )}
                                </>
                              );
                            })()}
                          </div>
                        )}
                    </div>
                    {message.role === "assistant" && undoSnapshot && (
                      <div className="flex justify-start">
                        <button
                          type="button"
                          onClick={() => onUndoSnapshot(undoSnapshot)}
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
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {mode === "execute" ||
        (mode === "plan" && isStreaming && thinkingInsertIndex === null) ? (
          <ThinkingPanel
            isStreaming={isStreaming}
            activeToolCalls={thinking.activeToolCalls}
            lastToolCalls={thinking.lastToolCalls}
            subKaniCalls={thinking.subKaniCalls}
            subKaniStatus={thinking.subKaniStatus}
            reasoning={thinking.reasoning}
            title={mode === "plan" ? "Thinking" : undefined}
          />
        ) : null}

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
