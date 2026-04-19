"use client";

import { AnimatePresence, motion } from "motion/react";
import { useRef, useState } from "react";
import { useEventListener } from "usehooks-ts";

import { cn } from "@/lib/utils/cn";

import type { Command } from "./types";

export interface SlashPopoverProps {
  open: boolean;
  query: string;
  commands: Command[];
  onSelect: (command: Command) => void;
  onDismiss: () => void;
}

function filterCommands(commands: Command[], query: string): Command[] {
  const lower = query.toLowerCase();
  if (lower === "") return commands;
  return commands.filter((c) => {
    if (c.name.toLowerCase().startsWith(lower)) return true;
    const aliases = c.aliases ?? [];
    return aliases.some((a) => a.toLowerCase().startsWith(lower));
  });
}

export function SlashPopover({
  open,
  query,
  commands,
  onSelect,
  onDismiss,
}: SlashPopoverProps) {
  const filtered = filterCommands(commands, query);

  const [activeIdx, setActiveIdx] = useState(0);
  const [filterKey, setFilterKey] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  // Render-time reset: when the filtered set changes identity we restart at 0
  // instead of firing an effect after paint.
  const nextFilterKey = `${query}|${filtered.length}`;
  if (filterKey !== nextFilterKey) {
    setFilterKey(nextFilterKey);
    setActiveIdx(0);
  }

  useEventListener("keydown", (event) => {
    if (!open) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIdx((i) =>
        filtered.length === 0 ? 0 : (i + 1) % filtered.length,
      );
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIdx((i) =>
        filtered.length === 0
          ? 0
          : (i - 1 + filtered.length) % filtered.length,
      );
      return;
    }
    if (event.key === "Enter" || event.key === "Tab") {
      const cmd = filtered[activeIdx];
      if (cmd !== undefined) {
        event.preventDefault();
        onSelect(cmd);
      }
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      onDismiss();
    }
  });

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
                {cmd.icon}
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
