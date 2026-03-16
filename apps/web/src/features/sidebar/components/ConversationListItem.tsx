import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreVertical } from "lucide-react";
import type { Strategy } from "@pathfinder/shared";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { formatSidebarTime } from "@/lib/formatTime";
import { Input } from "@/lib/components/ui/Input";

interface ConversationListItemProps {
  item: ConversationItem;
  isActive: boolean;
  isRenaming: boolean;
  renameValue: string;
  graphHasValidationIssue: boolean;
  /** True when this item is the active conversation AND a chat stream is in progress. */
  isActiveStreaming: boolean;
  onRenameValueChange: (value: string) => void;
  onCommitRename: (item: ConversationItem) => void;
  onCancelRename: () => void;
  onSelect: (item: ConversationItem) => void;
  onStartRename: (item: ConversationItem) => void;
  onStartDelete: (item: ConversationItem) => void;
  onStartDuplicate: (strategy: Strategy) => void;
  onToggleSaved: (strategy: Strategy) => void;
}

export function ConversationListItem({
  item,
  isActive,
  isRenaming,
  renameValue,
  graphHasValidationIssue,
  isActiveStreaming,
  onRenameValueChange,
  onCommitRename,
  onCancelRename,
  onSelect,
  onStartRename,
  onStartDelete,
  onStartDuplicate,
  onToggleSaved,
}: ConversationListItemProps) {
  const si = item.strategyItem;

  return (
    <div
      data-testid="conversation-item"
      data-conversation-id={item.id}
      className={`group flex w-full items-start justify-between gap-2 rounded-md border px-3 py-2 text-xs ${
        isActive
          ? "border-input bg-muted text-foreground"
          : "border-border bg-card text-muted-foreground hover:border-input hover:bg-muted"
      }`}
    >
      {isRenaming ? (
        <Input
          data-testid="conversation-rename-input"
          value={renameValue}
          onChange={(e) => onRenameValueChange(e.target.value)}
          onBlur={() => onCommitRename(item)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onCommitRename(item);
            }
            if (e.key === "Escape") onCancelRename();
          }}
          className="min-w-0 flex-1 bg-card px-1.5 py-0.5 font-medium"
          autoFocus
        />
      ) : (
        <button
          type="button"
          onClick={() => onSelect(item)}
          className="min-w-0 flex-1 text-left"
        >
          <div className="flex min-w-0 items-center gap-2">
            <span
              className="min-w-0 truncate text-sm font-medium text-foreground"
              title={item.title}
            >
              {item.title}
            </span>
            {si && graphHasValidationIssue && (
              <span
                className="inline-flex h-2 w-2 shrink-0 rounded-full bg-destructive/50"
                title="Validation issues"
              />
            )}
            {item.kind === "strategy" &&
              si &&
              (si.wdkStrategyId || (si.stepCount ?? 0) > 0) && (
                <span
                  className={`ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                    isActiveStreaming && !si.wdkStrategyId
                      ? "bg-warning/10 text-warning"
                      : si.isSaved
                        ? "bg-success/10 text-success"
                        : "bg-muted text-muted-foreground"
                  }`}
                >
                  {isActiveStreaming && !si.wdkStrategyId
                    ? "Building"
                    : si.isSaved
                      ? "Saved"
                      : "Draft"}
                </span>
              )}
          </div>
          <div className="text-xs text-muted-foreground">
            {formatSidebarTime(item.updatedAt)}
          </div>
        </button>
      )}

      {!isRenaming && (
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              className="ml-1 shrink-0 rounded-md p-1 text-muted-foreground opacity-0 transition hover:text-foreground group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="Conversation actions"
            >
              <MoreVertical className="h-4 w-4" aria-hidden="true" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              className="z-50 min-w-[160px] rounded-md border border-border bg-card p-1 text-sm text-foreground shadow-lg"
              sideOffset={4}
              align="end"
            >
              <DropdownMenu.Item
                className="cursor-pointer rounded px-2 py-1 outline-none hover:bg-muted focus:bg-muted"
                onSelect={() => onStartRename(item)}
              >
                Rename
              </DropdownMenu.Item>
              {si && (
                <>
                  <DropdownMenu.Item
                    className="cursor-pointer rounded px-2 py-1 outline-none hover:bg-muted focus:bg-muted"
                    onSelect={() => onStartDuplicate(si)}
                  >
                    Duplicate
                  </DropdownMenu.Item>
                  {si.wdkStrategyId && (
                    <DropdownMenu.Item
                      className="cursor-pointer rounded px-2 py-1 outline-none hover:bg-muted focus:bg-muted"
                      onSelect={() => onToggleSaved(si)}
                    >
                      {si.isSaved ? "Revert to draft" : "Mark as saved"}
                    </DropdownMenu.Item>
                  )}
                </>
              )}
              <DropdownMenu.Separator className="my-1 h-px bg-muted" />
              <DropdownMenu.Item
                className="cursor-pointer rounded px-2 py-1 text-destructive outline-none hover:bg-destructive/5 focus:bg-destructive/5"
                onSelect={() => onStartDelete(item)}
              >
                Delete
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      )}
    </div>
  );
}
