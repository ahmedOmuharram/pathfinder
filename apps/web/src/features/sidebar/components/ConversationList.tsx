"use client";

import { AnimatePresence, motion } from "motion/react";

import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { ConversationListItem } from "@/features/sidebar/components/ConversationListItem";
import { groupConversationsByTime } from "@/features/sidebar/lib/groupByTime";

interface ConversationListProps {
  items: ConversationItem[];
  query: string;
  hasInitiallyLoaded: boolean;
  activeId: string | null;
  renamingId: string | null;
  renameValue: string;
  chatIsStreaming: boolean;
  currentPhase: string | null;
  phaseStatus: string | null;
  onRenameValueChange: (v: string) => void;
  onCommitRename: (item: ConversationItem) => void;
  onCancelRename: () => void;
  onStartRename: (item: ConversationItem) => void;
  onStartDelete: (item: ConversationItem) => void;
  onStartDuplicate: (item: ConversationItem) => void;
  onToggleSaved: (item: ConversationItem) => void;
}

export function ConversationList({
  items,
  query,
  hasInitiallyLoaded,
  activeId,
  renamingId,
  renameValue,
  chatIsStreaming,
  currentPhase,
  phaseStatus,
  onRenameValueChange,
  onCommitRename,
  onCancelRename,
  onStartRename,
  onStartDelete,
  onStartDuplicate,
  onToggleSaved,
}: ConversationListProps) {
  const groups = groupConversationsByTime(items);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto pr-1">
      {items.length === 0 && hasInitiallyLoaded && (
        <div className="py-4 text-center text-sm text-muted-foreground">
          {query.trim()
            ? "No conversations match your search."
            : "No conversations yet. Click \u201cNew Chat\u201d to get started."}
        </div>
      )}
      <div className="space-y-4">
        <AnimatePresence initial={false}>
          {groups.map((group) => (
            <motion.div
              key={group.label}
              layout
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-1"
            >
              <div className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80">
                {group.label}
              </div>
              <AnimatePresence initial={false}>
                {group.items.map((item) => (
                  <motion.div
                    key={item.id}
                    layout
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                  >
                    <ConversationListItem
                      item={item}
                      isActive={activeId === item.id}
                      isRenaming={renamingId === item.id}
                      renameValue={renameValue}
                      isActiveStreaming={chatIsStreaming && activeId === item.id}
                      activePhase={currentPhase}
                      activePhaseStatus={phaseStatus}
                      onRenameValueChange={onRenameValueChange}
                      onCommitRename={onCommitRename}
                      onCancelRename={onCancelRename}
                      onStartRename={onStartRename}
                      onStartDelete={onStartDelete}
                      onStartDuplicate={onStartDuplicate}
                      onToggleSaved={onToggleSaved}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
