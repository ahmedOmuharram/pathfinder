import { MoreVertical } from "lucide-react";
import Link from "next/link";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { formatSidebarTime } from "@/lib/formatTime";

interface ConversationListItemProps {
  item: ConversationItem;
  isActive: boolean;
  isRenaming: boolean;
  renameValue: string;
  isActiveStreaming: boolean;
  activePhase: string | null;
  activePhaseStatus: string | null;
  onRenameValueChange: (value: string) => void;
  onCommitRename: (item: ConversationItem) => void;
  onCancelRename: () => void;
  onStartRename: (item: ConversationItem) => void;
  onStartDelete: (item: ConversationItem) => void;
  onStartDuplicate: (item: ConversationItem) => void;
  onToggleSaved: (item: ConversationItem) => void;
}

export function ConversationListItem({
  item,
  isActive,
  isRenaming,
  renameValue,
  isActiveStreaming,
  onRenameValueChange,
  onCommitRename,
  onCancelRename,
  onStartRename,
  onStartDelete,
  onStartDuplicate,
  onToggleSaved,
}: ConversationListItemProps) {
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
          className="h-7 min-w-0 flex-1 bg-card px-1.5 py-0.5 font-medium"
          autoFocus
        />
      ) : (
        <Link
          href={`/conversation/${item.id}`}
          className="min-w-0 flex-1 text-left"
        >
          <div className="flex min-w-0 items-center gap-2">
            <span
              className="min-w-0 truncate text-sm font-medium text-foreground"
              title={item.title}
            >
              {item.title}
            </span>
            <span className="ml-auto text-xs text-muted-foreground">
              {item.stepCount} step{item.stepCount === 1 ? "" : "s"}
              {isActiveStreaming ? " · streaming" : ""}
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            {formatSidebarTime(item.updatedAt)}
          </div>
        </Link>
      )}

      {!isRenaming && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              aria-label="Conversation actions"
              className="ml-1 shrink-0 opacity-0 transition group-hover:opacity-100 focus-visible:opacity-100"
            >
              <MoreVertical className="h-4 w-4" aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" sideOffset={4} className="min-w-[160px]">
            <DropdownMenuItem onSelect={() => onStartRename(item)}>
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => onStartDuplicate(item)}>
              Duplicate
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => onToggleSaved(item)}>
              {item.isSaved ? "Unmark saved" : "Mark as saved"}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => onStartDelete(item)}>
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
