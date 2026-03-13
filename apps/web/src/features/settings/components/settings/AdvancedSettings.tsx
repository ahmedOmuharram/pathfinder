"use client";

/**
 * AdvancedSettings -- debug toggles.
 */

import { useSettingsStore } from "@/state/useSettingsStore";
import { SettingsField } from "./SettingsField";

export function AdvancedSettings() {
  const showRawToolCalls = useSettingsStore((s) => s.showRawToolCalls);
  const setShowRawToolCalls = useSettingsStore((s) => s.setShowRawToolCalls);
  const showTokenUsage = useSettingsStore((s) => s.showTokenUsage);
  const setShowTokenUsage = useSettingsStore((s) => s.setShowTokenUsage);
  const syncDeleteToWdk = useSettingsStore((s) => s.syncDeleteToWdk);
  const setSyncDeleteToWdk = useSettingsStore((s) => s.setSyncDeleteToWdk);
  const resetToDefaults = useSettingsStore((s) => s.resetToDefaults);

  return (
    <div className="space-y-5">
      <SettingsField label="Show token usage">
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showTokenUsage}
            onChange={(e) => setShowTokenUsage(e.target.checked)}
            className="h-4 w-4 rounded border-input text-foreground focus:ring-ring"
          />
          <span className="text-muted-foreground">
            Display token counts under each message
          </span>
        </label>
      </SettingsField>

      <SettingsField label="Show raw tool calls in chat">
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showRawToolCalls}
            onChange={(e) => setShowRawToolCalls(e.target.checked)}
            className="h-4 w-4 rounded border-input text-foreground focus:ring-ring"
          />
          <span className="text-muted-foreground">
            Display raw JSON tool calls in the chat log
          </span>
        </label>
      </SettingsField>

      <SettingsField label="Sync strategy deletion to WDK">
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
          <input
            data-testid="sync-delete-to-wdk-checkbox"
            type="checkbox"
            checked={syncDeleteToWdk}
            onChange={(e) => setSyncDeleteToWdk(e.target.checked)}
            className="h-4 w-4 rounded border-input text-foreground focus:ring-ring"
          />
          <span className="text-muted-foreground">
            When enabled, deleting a strategy also removes it from VEuPathDB
          </span>
        </label>
      </SettingsField>

      <div className="border-t border-border pt-4">
        <button
          type="button"
          onClick={resetToDefaults}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:bg-muted"
        >
          Reset all settings to defaults
        </button>
      </div>
    </div>
  );
}
