"use client";

/**
 * Renders the filtered/sorted list of conversation items.
 *
 * Pure presentational component — all data and action callbacks
 * are received via props from the parent sidebar.
 */

import { useStrategyList } from "@/state/useStrategySelectors";
import type { Strategy } from "@pathfinder/shared";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { ConversationListItem } from "@/features/sidebar/components/ConversationListItem";

interface ConversationListProps {
  items: ConversationItem[];
  query: string;
  hasInitiallyLoaded: boolean;
  activeId: string | null;
  renamingId: string | null;
  renameValue: string;
  /** Whether a chat stream is currently in progress. */
  chatIsStreaming: boolean;
  onRenameValueChange: (v: string) => void;
  onCommitRename: (item: ConversationItem) => void;
  onCancelRename: () => void;
  onSelect: (item: ConversationItem) => void;
  onStartRename: (item: ConversationItem) => void;
  onStartDelete: (item: ConversationItem) => void;
  onStartDuplicate: (strategy: Strategy) => void;
  onToggleSaved: (strategy: Strategy) => void;
}

export function ConversationList({
  items,
  query,
  hasInitiallyLoaded,
  activeId,
  renamingId,
  renameValue,
  chatIsStreaming,
  onRenameValueChange,
  onCommitRename,
  onCancelRename,
  onSelect,
  onStartRename,
  onStartDelete,
  onStartDuplicate,
  onToggleSaved,
}: ConversationListProps) {
  const { graphValidationStatus } = useStrategyList();

  return (
    <div className="min-h-0 flex-1 overflow-y-auto pr-1">
      <div className="space-y-1">
        {items.length === 0 && hasInitiallyLoaded && (
          <div className="py-4 text-center text-sm text-muted-foreground">
            {query.trim()
              ? "No conversations match your search."
              : "No conversations yet. Click \u201cNew Chat\u201d to get started."}
          </div>
        )}
        {items.map((item) => {
          const si = item.strategyItem;
          return (
            <ConversationListItem
              key={item.id}
              item={item}
              isActive={activeId === item.id}
              isRenaming={renamingId === item.id}
              renameValue={renameValue}
              graphHasValidationIssue={Boolean(si && graphValidationStatus[si.id])}
              isActiveStreaming={chatIsStreaming && activeId === item.id}
              onRenameValueChange={onRenameValueChange}
              onCommitRename={onCommitRename}
              onCancelRename={onCancelRename}
              onSelect={onSelect}
              onStartRename={onStartRename}
              onStartDelete={onStartDelete}
              onStartDuplicate={onStartDuplicate}
              onToggleSaved={onToggleSaved}
            />
          );
        })}
      </div>
    </div>
  );
}
