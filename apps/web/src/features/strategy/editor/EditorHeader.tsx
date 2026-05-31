"use client";

import { useState } from "react";
import { Bookmark, Copy, MoreVertical, Trash2, Code2 } from "lucide-react";
import type { Step, StepKind } from "@pathfinder/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils/cn";

interface EditorHeaderProps {
  step: Step;
  kind: StepKind;
  stepNumber: number | null;
  onRename: (next: string) => void;
  onDelete: () => void;
  onDuplicate: () => void;
  onCopyUrl: () => void;
  onSaveAsReusable: () => void;
}

const KIND_BG: Record<StepKind, string> = {
  search: "bg-emerald-100 text-emerald-900 hover:bg-emerald-100",
  combine: "bg-indigo-100 text-indigo-900 hover:bg-indigo-100",
  transform: "bg-violet-100 text-violet-900 hover:bg-violet-100",
};

const isDevEnv = process.env.NODE_ENV === "development";

export function EditorHeader({
  step,
  kind,
  stepNumber,
  onRename,
  onDelete,
  onDuplicate,
  onCopyUrl,
  onSaveAsReusable,
}: EditorHeaderProps) {
  const initialName = step.displayName ?? "";
  const [draft, setDraft] = useState(initialName);
  const [showRaw, setShowRaw] = useState(false);

  const [prevInitial, setPrevInitial] = useState(initialName);
  if (initialName !== prevInitial) {
    setPrevInitial(initialName);
    setDraft(initialName);
  }

  const commit = (): void => {
    const next = draft.trim();
    if (next === "" || next === initialName) {
      setDraft(initialName);
      return;
    }
    onRename(next);
  };

  const cancel = (): void => {
    setDraft(initialName);
  };

  return (
    <div className="flex items-center gap-2 border-b border-border px-4 py-3">
      <Badge
        variant="secondary"
        className={cn("uppercase tracking-wide", KIND_BG[kind])}
      >
        {kind}
      </Badge>
      {stepNumber != null && (
        <span className="text-xs text-muted-foreground">Step {stepNumber}</span>
      )}
      <Input
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.currentTarget.blur();
          } else if (event.key === "Escape") {
            cancel();
            event.currentTarget.blur();
          }
        }}
        onFocus={(event) => event.currentTarget.select()}
        aria-label="Step name"
        className="h-8 flex-1"
      />
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="More actions"
          >
            <MoreVertical className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[180px]">
          <DropdownMenuItem onSelect={onDuplicate}>
            <Copy className="size-4" />
            Duplicate step
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={onCopyUrl}>
            <Copy className="size-4" />
            Copy step URL
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={onSaveAsReusable}
            data-testid="step-editor-save-substrategy"
          >
            <Bookmark className="size-4" />
            Save as reusable…
          </DropdownMenuItem>
          {isDevEnv && (
            <DropdownMenuItem onSelect={() => setShowRaw((prev) => !prev)}>
              <Code2 className="size-4" />
              {showRaw ? "Hide" : "Show"} raw JSON
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={onDelete}>
            <Trash2 className="size-4" />
            Delete step
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {isDevEnv && showRaw && (
        <pre className="absolute right-4 top-14 z-10 max-w-md rounded border border-border bg-popover p-2 text-[10px] text-popover-foreground shadow">
          {JSON.stringify(step, null, 2)}
        </pre>
      )}
    </div>
  );
}
