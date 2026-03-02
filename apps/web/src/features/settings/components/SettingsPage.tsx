"use client";

/**
 * SettingsPage -- modal-based settings with General, Data, and Advanced tabs.
 *
 * Each tab's content is extracted into its own component under ./settings/.
 */

import { useState } from "react";
import { Modal } from "@/lib/components/Modal";
import { GeneralSettings } from "./settings/GeneralSettings";
import { DataSettings } from "./settings/DataSettings";
import { AdvancedSettings } from "./settings/AdvancedSettings";

type Tab = "general" | "data" | "advanced";

const TABS: { id: Tab; label: string }[] = [
  { id: "general", label: "General" },
  { id: "data", label: "Data" },
  { id: "advanced", label: "Advanced" },
];

interface SettingsPageProps {
  open: boolean;
  onClose: () => void;
  /** Site ID for scoped delete operations. */
  siteId: string;
  /** Refresh plan list after clearing plans. */
  onPlansCleared?: () => void;
  /** Refresh strategy list after clearing strategies. */
  onStrategiesCleared?: () => void;
}

export function SettingsPage({
  open,
  onClose,
  siteId,
  onPlansCleared,
  onStrategiesCleared,
}: SettingsPageProps) {
  const [tab, setTab] = useState<Tab>("general");

  return (
    <Modal open={open} onClose={onClose} title="Settings" maxWidth="max-w-lg">
      <div className="flex min-h-[340px] flex-col">
        {/* Tabs */}
        <div className="flex border-b border-border px-5">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-sm font-semibold transition-colors ${
                tab === t.id
                  ? "border-b-2 border-primary text-foreground"
                  : "text-muted-foreground hover:text-muted-foreground"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {tab === "general" && <GeneralSettings />}
          {tab === "data" && (
            <DataSettings
              siteId={siteId}
              onPlansCleared={onPlansCleared}
              onStrategiesCleared={onStrategiesCleared}
            />
          )}
          {tab === "advanced" && <AdvancedSettings />}
        </div>
      </div>
    </Modal>
  );
}
