"use client";

/**
 * SettingsPage -- modal-based settings with Model, Data, Advanced, and Seeding tabs.
 */

import { useState } from "react";
import { Modal } from "@/lib/components/Modal";
import { GeneralSettings } from "./settings/GeneralSettings";
import { DataSettings } from "./settings/DataSettings";
import { AdvancedSettings } from "./settings/AdvancedSettings";
import { SeedingSettings } from "./settings/SeedingSettings";

type Tab = "general" | "data" | "advanced" | "seeding";

const TABS: { id: Tab; label: string }[] = [
  { id: "general", label: "Model" },
  { id: "data", label: "Data" },
  { id: "advanced", label: "Advanced" },
  { id: "seeding", label: "Seeding" },
];

interface SettingsPageProps {
  open: boolean;
  onClose: () => void;
  siteId: string;
}

export function SettingsPage({ open, onClose, siteId }: SettingsPageProps) {
  const [tab, setTab] = useState<Tab>("general");

  return (
    <Modal open={open} onClose={onClose} title="Settings" maxWidth="max-w-2xl" showCloseButton>
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
        {tab === "general" && <GeneralSettings />}
        {tab === "data" && <DataSettings siteId={siteId} />}
        {tab === "advanced" && <AdvancedSettings />}
        {tab === "seeding" && <SeedingSettings />}
      </div>
    </Modal>
  );
}
