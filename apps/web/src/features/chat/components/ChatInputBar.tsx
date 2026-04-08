import { X } from "lucide-react";
import type { ChatMention } from "@pathfinder/shared";
import type { NodeSelection } from "@/lib/types/nodeSelection";
import { DraftSelectionBar } from "@/features/chat/components/delegation/DraftSelectionBar";
import { MessageComposer } from "@/features/chat/components/MessageComposer";

interface ChatInputBarProps {
  apiError: string | null;
  onDismissError: () => void;
  draftSelection: NodeSelection | null;
  onRemoveDraft: () => void;
  onSend: (message: string, mentions?: ChatMention[]) => void;
  isStreaming: boolean;
  onStop: () => void;
  onOpenEngine?: (() => void) | undefined;
  siteId: string;
}

export function ChatInputBar({
  apiError,
  onDismissError,
  draftSelection,
  onRemoveDraft,
  onSend,
  isStreaming,
  onStop,
  onOpenEngine,
  siteId,
}: ChatInputBarProps) {
  return (
    <div className="border-t border-border bg-card p-3">
      {apiError !== null && apiError !== "" && (
        <div
          role="alert"
          aria-live="assertive"
          className="mb-3 flex items-start justify-between gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
        >
          <p>{apiError}</p>
          <button
            type="button"
            onClick={onDismissError}
            aria-label="Dismiss error"
            className="shrink-0 rounded p-0.5 text-destructive/50 transition-colors hover:text-destructive"
          >
            <X className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      )}
      {draftSelection && (
        <DraftSelectionBar selection={draftSelection} onRemove={onRemoveDraft} />
      )}
      <MessageComposer
        onSend={onSend}
        disabled={isStreaming}
        isStreaming={isStreaming}
        onStop={onStop}
        onOpenEngine={onOpenEngine}
        siteId={siteId}
      />
    </div>
  );
}
