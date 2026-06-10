"use client";

import { Bookmark, MoreVertical, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface CompactRowKebabProps {
  stepId: string;
  onSaveStep?: (stepId: string) => void;
  onInsertSavedAt?: (stepId: string) => void;
}

export function CompactRowKebab({
  stepId,
  onSaveStep,
  onInsertSavedAt,
}: CompactRowKebabProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Step actions"
          className="size-6"
          data-testid={`compact-step-kebab-${stepId}`}
        >
          <MoreVertical className="size-3" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[180px]">
        {onSaveStep != null && (
          <DropdownMenuItem onSelect={() => onSaveStep(stepId)}>
            <Bookmark className="size-4" />
            Save as reusable...
          </DropdownMenuItem>
        )}
        {onInsertSavedAt != null && (
          <DropdownMenuItem onSelect={() => onInsertSavedAt(stepId)}>
            <Plus className="size-4" />
            Insert saved here...
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
