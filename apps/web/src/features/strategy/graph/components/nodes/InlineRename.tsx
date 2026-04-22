"use client";

import { useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils/cn";

interface InlineRenameProps {
  value: string;
  onCommit: (next: string) => void;
  onCancel: () => void;
  className?: string;
  inputClassName?: string;
}

export function InlineRename({
  value,
  onCommit,
  onCancel,
  className,
  inputClassName,
}: InlineRenameProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const cancelledRef = useRef(false);

  function startEditing(event: React.MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    cancelledRef.current = false;
    setDraft(value);
    setEditing(true);
  }

  function focusAndSelect(node: HTMLInputElement | null) {
    if (node == null) return;
    node.focus();
    node.select();
  }

  function commit() {
    setEditing(false);
    onCommit(draft);
  }

  function cancel() {
    cancelledRef.current = true;
    setDraft(value);
    setEditing(false);
    onCancel();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      cancel();
    }
  }

  function handleBlur() {
    if (cancelledRef.current) {
      cancelledRef.current = false;
      return;
    }
    if (!editing) return;
    commit();
  }

  if (!editing) {
    return (
      <button
        type="button"
        data-testid="inline-rename-trigger"
        onClick={startEditing}
        className={cn(
          "block w-full truncate text-left text-sm font-medium leading-tight text-foreground hover:underline",
          className,
        )}
      >
        {value}
      </button>
    );
  }

  return (
    <Input
      ref={focusAndSelect}
      data-testid="inline-rename-input"
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={handleBlur}
      onClick={(event) => event.stopPropagation()}
      className={cn("h-7 px-1.5 py-0.5 text-sm font-medium", inputClassName)}
    />
  );
}
