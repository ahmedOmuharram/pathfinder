import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreVertical } from "lucide-react";
import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { formatSidebarTime } from "@/lib/formatTime";

interface ConversationListItemProps {
  item: ConversationItem;
  isActive: boolean;
  isRenaming: boolean;
  renameValue: string;
  graphHasValidationIssue: boolean;
  onRenameValueChange: (value: string) => void;
  onCommitRename: (item: ConversationItem) => void;
  onCancelRename: () => void;
  onSelect: (item: ConversationItem) => void;
  onStartRename: (item: ConversationItem) => void;
  onStartDelete: (item: ConversationItem) => void;
  onStartDuplicate: (strategy: StrategyListItem) => void;
  onToggleSaved: (strategy: StrategyListItem) => void;
}

export function ConversationListItem({
  item,
  isActive,
  isRenaming,
  renameValue,
  graphHasValidationIssue,
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
        <input
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
          className="min-w-0 flex-1 rounded border border-input bg-card px-1.5 py-0.5 text-sm font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          autoFocus
        />
      ) : (
        <button
          type="button"
          onClick={() => onSelect(item)}
          className="min-w-0 flex-1 text-left"
        >
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-foreground">
              {item.title}
            </span>
            {item.kind === "strategy" && si && (
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${
                  !si.wdkStrategyId
                    ? "bg-amber-100 text-amber-700"
                    : si.isSaved
                      ? "bg-emerald-100 text-success"
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {!si.wdkStrategyId ? "Building" : si.isSaved ? "Saved" : "Draft"}
              </span>
            )}
            {si && graphHasValidationIssue && (
              <span
                className="inline-flex h-2 w-2 shrink-0 rounded-full bg-destructive/50"
                title="Validation issues"
              />
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
              className="ml-1 shrink-0 rounded-md p-1 text-muted-foreground opacity-0 transition hover:text-foreground group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
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
