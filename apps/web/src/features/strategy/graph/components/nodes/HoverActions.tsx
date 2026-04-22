"use client";

import { Code2, MessageSquarePlus, MoreVertical, Pencil } from "lucide-react";
import type { Step } from "@pathfinder/shared";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const isDev = process.env.NODE_ENV !== "production";

export type HoverActionsProps = {
  step: Step;
  onAddToChat?: ((stepId: string) => void) | undefined;
  onOpenDetails?: ((stepId: string) => void) | undefined;
  onDuplicate?: ((stepId: string) => void) | undefined;
  onDelete?: ((stepId: string) => void) | undefined;
};

export function HoverActions({
  step,
  onAddToChat,
  onOpenDetails,
  onDuplicate,
  onDelete,
}: HoverActionsProps) {
  function copyId(event: Event) {
    event.stopPropagation();
    void navigator.clipboard.writeText(step.id);
  }

  function copyRawJson(event: Event) {
    event.stopPropagation();
    void navigator.clipboard.writeText(JSON.stringify(step, null, 2));
  }

  return (
    <div className="absolute right-1.5 top-1.5 z-20 flex items-center gap-1 rounded-md border border-border bg-card/95 px-0.5 py-0.5 opacity-0 shadow-sm backdrop-blur-sm transition-opacity duration-150 group-hover:opacity-100 focus-within:opacity-100 aria-expanded:opacity-100 group-data-[selected=true]:opacity-100">
      {onOpenDetails != null && (
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="Edit step"
          data-testid={`rf-edit-${step.id}`}
          onClick={(event) => {
            event.stopPropagation();
            onOpenDetails(step.id);
          }}
        >
          <Pencil className="size-3" aria-hidden="true" />
        </Button>
      )}
      {onAddToChat != null && (
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="Add to chat"
          data-testid={`rf-add-to-chat-${step.id}`}
          onClick={(event) => {
            event.stopPropagation();
            onAddToChat(step.id);
          }}
        >
          <MessageSquarePlus className="size-3" aria-hidden="true" />
        </Button>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label="More actions"
            data-testid={`rf-more-${step.id}`}
            onClick={(event) => event.stopPropagation()}
          >
            <MoreVertical className="size-3" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" sideOffset={4}>
          {onDuplicate != null && (
            <DropdownMenuItem
              onSelect={(event) => {
                event.stopPropagation();
                onDuplicate(step.id);
              }}
            >
              Duplicate step
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onSelect={copyId}>Copy step ID</DropdownMenuItem>
          {isDev && (
            <DropdownMenuItem onSelect={copyRawJson}>
              <Code2 className="size-3" aria-hidden="true" />
              Copy raw JSON
            </DropdownMenuItem>
          )}
          {onDelete != null && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                variant="destructive"
                onSelect={(event) => {
                  event.stopPropagation();
                  onDelete(step.id);
                }}
              >
                Delete step
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
