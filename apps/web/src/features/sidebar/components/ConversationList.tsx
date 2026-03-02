"use client";

/**
 * Renders the filtered/sorted list of conversation items.
 *
 * Pure presentational component — all data and action callbacks
 * are received via props from the parent sidebar.
 */

import { useStrategyListStore } from "@/state/useStrategyListStore";
import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { ConversationListItem } from "@/features/sidebar/components/ConversationListItem";

interface ConversationListProps {
  items: ConversationItem[];
  query: string;
  activeId: string | null;
  renamingId: string | null;
  renameValue: string;
  onRenameValueChange: (v: string) => void;
  onCommitRename: (item: ConversationItem) => void;
  onCancelRename: () => void;
  onSelect: (item: ConversationItem) => void;
  onStartRename: (item: ConversationItem) => void;
  onStartDelete: (item: ConversationItem) => void;
  onStartDuplicate: (strategy: StrategyListItem) => void;
  onToggleSaved: (strategy: StrategyListItem) => void;
}

export function ConversationList({
  items,
  query,
  activeId,
  renamingId,
  renameValue,
  onRenameValueChange,
  onCommitRename,
  onCancelRename,
  onSelect,
  onStartRename,
  onStartDelete,
  onStartDuplicate,
  onToggleSaved,
}: ConversationListProps) {
  const graphValidationStatus = useStrategyListStore((s) => s.graphValidationStatus);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto pr-1">
      <div className="space-y-1">
        {items.length === 0 && (
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
