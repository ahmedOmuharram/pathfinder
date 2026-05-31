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
import { useFlushBeforeNav } from "@/features/strategy/hooks/useFlushBeforeNav";
import { formatSidebarTime } from "@/lib/formatTime";
import { cn } from "@/lib/utils/cn";

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
  onToggleSaved,
}: ConversationListItemProps) {
  const { navigate } = useFlushBeforeNav();
  const metaParts: string[] = [];
  if (item.stepCount > 0) {
    metaParts.push(`${item.stepCount} step${item.stepCount === 1 ? "" : "s"}`);
  }
  metaParts.push(formatSidebarTime(item.updatedAt));

  return (
    <div
      data-testid="conversation-item"
      data-conversation-id={item.id}
      className={cn(
        "group relative rounded-md px-2.5 py-1.5 transition-colors",
        isActive
          ? "bg-primary/15 text-primary hover:bg-primary/20"
          : "text-foreground/85 hover:bg-muted/60",
      )}
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
          className="h-7 min-w-0 bg-card px-1.5 py-0.5 font-medium"
          autoFocus
        />
      ) : (
        <>
          <Link
            href={`/${item.siteId}/conversation/${item.id}`}
            className="block"
            onClick={(e) => {
              if (isActive) return;
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
              if (e.button !== 0) return;
              e.preventDefault();
              void navigate(`/${item.siteId}/conversation/${item.id}`);
            }}
          >
            <div className="truncate pr-6 text-sm font-medium" title={item.title}>
              {item.title}
            </div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {metaParts.join(" · ")}
              {isActiveStreaming && (
                <>
                  {" · "}
                  <span className="text-primary">streaming</span>
                </>
              )}
            </div>
          </Link>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                aria-label="Conversation actions"
                className="absolute right-1 top-1 opacity-0 transition group-hover:opacity-100 focus-visible:opacity-100 aria-expanded:opacity-100"
              >
                <MoreVertical className="h-3.5 w-3.5" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" sideOffset={4} className="min-w-[160px]">
              <DropdownMenuItem onSelect={() => onStartRename(item)}>
                Rename
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onToggleSaved(item)}>
                {item.isSaved ? "Unmark saved" : "Mark as saved"}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                variant="destructive"
                onSelect={() => onStartDelete(item)}
              >
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </>
      )}
    </div>
  );
}
