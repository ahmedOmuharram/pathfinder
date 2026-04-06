import { ArrowDown, FileText, FlaskConical } from "lucide-react";
import type { ChatMention } from "@pathfinder/shared";
import type { NodeSelection } from "@/lib/types/nodeSelection";
import { ChatMarkdown } from "@/lib/components/ChatMarkdown";
import { NodeCard } from "@/features/chat/components/delegation/NodeCard";
import { formatMessageTime } from "@/lib/formatTime";

export function MentionChips({ mentions }: { mentions: ChatMention[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {mentions.map((m) => {
        const Icon = m.type === "strategy" ? FileText : FlaskConical;
        return (
          <span
            key={`${m.type}-${m.id}`}
            className="inline-flex items-center gap-1 rounded-md bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary-foreground ring-1 ring-inset ring-primary/30"
          >
            <Icon className="h-2.5 w-2.5 shrink-0" />
            {m.displayName}
          </span>
        );
      })}
    </div>
  );
}

export function ChatLoadingSkeleton() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 animate-fade-in">
      <div className="flex gap-1.5">
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:150ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:300ms]" />
      </div>
      <p className="text-xs text-muted-foreground">Loading conversation...</p>
    </div>
  );
}

export function MessageTimestamp({ iso }: { iso: string }) {
  const text = formatMessageTime(iso);
  if (!text) return null;
  return (
    <span className="mt-2 block text-xs leading-none text-muted-foreground select-none">
      {text}
    </span>
  );
}

export function UndoButton({
  onClick,
  disabled,
}: {
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-input hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
      title="Undo from this message"
      aria-label="Undo from this message"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-3.5 w-3.5">
        <path d="M9 14L4 9l5-5" />
        <path d="M20 20v-5a7 7 0 0 0-7-7H4" />
      </svg>
      Undo
    </button>
  );
}

export function ScrollToBottomButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Scroll to bottom"
      className="absolute bottom-4 left-1/2 z-10 -translate-x-1/2 rounded-full border border-border bg-card p-2 shadow-md transition-colors hover:bg-accent"
    >
      <ArrowDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
    </button>
  );
}

export function UserMessageBody({
  nodeData,
  nodeList,
  nodeIds,
  hasText,
  decodedMessage,
  rawContent,
  mentions,
}: {
  nodeData: NodeSelection | null;
  nodeList: NodeSelection["nodes"];
  nodeIds: NodeSelection["nodeIds"];
  hasText: boolean;
  decodedMessage: string;
  rawContent: string;
  mentions: ChatMention[] | undefined;
}) {
  const hasMentions = mentions != null && mentions.length > 0;
  if (nodeData) {
    return (
      <div className="space-y-1">
        {hasMentions ? <MentionChips mentions={mentions} /> : null}
        <div className="flex w-full gap-2 overflow-x-auto pb-1">
          {nodeList.map((node: NodeSelection["nodes"][number], nodeIndex: number) => (
            <div
              key={`${nodeIds[nodeIndex] ?? nodeIndex}`}
              className="shrink-0 min-w-[220px]"
            >
              <NodeCard node={node} />
            </div>
          ))}
        </div>
        {hasText ? (
          <div className="rounded-lg bg-primary px-3 py-2 text-primary-foreground selection:bg-primary-foreground selection:text-primary">
            <ChatMarkdown content={decodedMessage} tone="onDark" />
          </div>
        ) : null}
      </div>
    );
  }
  return (
    <div className="space-y-1">
      {hasMentions ? <MentionChips mentions={mentions} /> : null}
      <div className="rounded-lg px-3 py-2 bg-primary text-primary-foreground selection:bg-primary-foreground selection:text-primary">
        <ChatMarkdown content={rawContent} tone="onDark" />
      </div>
    </div>
  );
}
