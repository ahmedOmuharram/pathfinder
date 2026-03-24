"use client";

import { useState, useEffect, useCallback } from "react";
import { Wrench, X } from "lucide-react";
import { listTools, type ToolItem } from "@/lib/api/tools";
import { useSettingsStore } from "@/state/useSettingsStore";

export function ToolPicker({ disabled }: { disabled?: boolean }) {
  const [tools, setTools] = useState<ToolItem[]>([]);
  const [open, setOpen] = useState(false);
  const disabledTools = useSettingsStore((s) => s.disabledTools);
  const toggleTool = useSettingsStore((s) => s.toggleTool);
  const setDisabledTools = useSettingsStore((s) => s.setDisabledTools);

  useEffect(() => {
    listTools()
      .then(setTools)
      .catch((err) => console.warn("[ToolPicker] Failed to load tools:", err));
  }, []);

  const enabledCount = tools.length - disabledTools.length;

  const enableAll = useCallback(() => setDisabledTools([]), [setDisabledTools]);
  const disableAll = useCallback(
    () => setDisabledTools(tools.map((t) => t.name)),
    [setDisabledTools, tools],
  );

  if (tools.length === 0) return null;

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs font-medium text-foreground transition hover:border-input hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
        aria-label={`${enabledCount} of ${tools.length} tools enabled`}
      >
        <Wrench className="h-3 w-3 text-muted-foreground" aria-hidden />
        <span>
          {enabledCount}/{tools.length}
        </span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div className="relative mx-4 flex max-h-[80vh] w-full max-w-md flex-col rounded-lg border border-border bg-card shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div>
                <h2 className="text-sm font-semibold text-foreground">AI Tools</h2>
                <p className="text-xs text-muted-foreground">
                  {enabledCount} of {tools.length} enabled
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={enableAll}
                  className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent"
                >
                  All on
                </button>
                <button
                  type="button"
                  onClick={disableAll}
                  className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent"
                >
                  All off
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded p-1 text-muted-foreground hover:bg-accent"
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Tool list */}
            <div className="flex-1 overflow-y-auto p-2">
              {tools.map((tool) => {
                const isEnabled = !disabledTools.includes(tool.name);
                return (
                  <label
                    key={tool.name}
                    className="flex cursor-pointer items-start gap-3 rounded-md px-2 py-2 transition hover:bg-accent"
                  >
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      onChange={() => toggleTool(tool.name)}
                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-input text-foreground focus:ring-ring"
                    />
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-foreground">
                        {tool.name}
                      </div>
                      {tool.description && (
                        <div className="text-xs text-muted-foreground line-clamp-2">
                          {tool.description}
                        </div>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
