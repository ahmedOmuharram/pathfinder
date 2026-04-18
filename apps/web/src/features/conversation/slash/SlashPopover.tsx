"use client";

import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils/cn";

import type { Command } from "./types";

export interface SlashPopoverProps {
  open: boolean;
  query: string;
  commands: Command[];
  onSelect: (command: Command) => void;
  onDismiss: () => void;
}

export function SlashPopover({
  open,
  query,
  commands,
  onSelect,
  onDismiss,
}: SlashPopoverProps) {
  const filtered = useMemo(() => {
    const lower = query.toLowerCase();
    if (lower === "") return commands;
    return commands.filter((c) => {
      if (c.name.toLowerCase().startsWith(lower)) return true;
      return c.aliases?.some((a) =>
        a.toLowerCase().startsWith(lower),
      ) ?? false;
    });
  }, [query, commands]);

  const [activeIdx, setActiveIdx] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setActiveIdx(0);
  }, [query, filtered.length]);

  useEffect(() => {
    if (!open) return undefined;
    const el = listRef.current;
    if (el === null) return undefined;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) =>
          filtered.length === 0 ? 0 : (i + 1) % filtered.length,
        );
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) =>
          filtered.length === 0
            ? 0
            : (i - 1 + filtered.length) % filtered.length,
        );
      } else if (e.key === "Enter" || e.key === "Tab") {
        const cmd = filtered[activeIdx];
        if (cmd !== undefined) {
          e.preventDefault();
          onSelect(cmd);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        onDismiss();
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [open, filtered, activeIdx, onSelect, onDismiss]);

  return (
    <AnimatePresence>
      {open && filtered.length > 0 && (
        <motion.div
          key="slash-popover"
          ref={listRef}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 6 }}
          transition={{ duration: 0.12 }}
          data-testid="slash-popover"
          className={cn(
            "absolute bottom-full left-0 right-0 z-20 mb-2",
            "max-h-72 overflow-y-auto rounded-lg border border-border bg-popover",
            "shadow-[var(--shadow-float)]",
          )}
        >
          {filtered.map((cmd, i) => (
            <button
              key={cmd.name}
              type="button"
              data-testid={`slash-item-${cmd.name}`}
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => onSelect(cmd)}
              className={cn(
                "flex w-full items-center gap-3 px-3 py-2 text-left text-sm transition-colors",
                i === activeIdx
                  ? "bg-accent text-accent-foreground"
                  : "text-foreground",
              )}
            >
              <span className="text-muted-foreground">
                {cmd.icon as ReactNode}
              </span>
              <span className="font-mono text-[12px] font-medium">
                /{cmd.name}
              </span>
              <span className="truncate text-[12px] text-muted-foreground">
                {cmd.description}
              </span>
            </button>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
