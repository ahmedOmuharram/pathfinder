"use client";

/**
 * SettingsPage -- modal-based settings with Data, Advanced, and Seeding tabs.
 */

import { useState } from "react";
import { Modal } from "@/lib/components/Modal";
import { DataSettings } from "./settings/DataSettings";
import { AdvancedSettings } from "./settings/AdvancedSettings";
import { SeedingSettings } from "./settings/SeedingSettings";
import { MemorySettings } from "./settings/MemorySettings";

type Tab = "data" | "memory" | "advanced" | "seeding";

const TABS: { id: Tab; label: string }[] = [
  { id: "data", label: "Data" },
  { id: "memory", label: "Memory" },
  { id: "advanced", label: "Advanced" },
  { id: "seeding", label: "Seeding" },
];

interface SettingsPageProps {
  open: boolean;
  onClose: () => void;
  siteId: string;
}

export function SettingsPage({ open, onClose, siteId }: SettingsPageProps) {
  const [tab, setTab] = useState<Tab>("data");

  return (
    <Modal open={open} onClose={onClose} title="Settings" maxWidth="max-w-3xl" showCloseButton>
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
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content — scrollable */}
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {tab === "data" && <DataSettings siteId={siteId} />}
        {tab === "memory" && <MemorySettings />}
        {tab === "advanced" && <AdvancedSettings />}
        {tab === "seeding" && <SeedingSettings />}
      </div>
    </Modal>
  );
}
