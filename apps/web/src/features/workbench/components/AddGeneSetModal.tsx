"use client";

import { useCallback, useState } from "react";
import { Modal } from "@/lib/components/Modal";
import { cn } from "@/lib/utils/cn";
import { AddGeneSetPasteTab } from "./AddGeneSetPasteTab";
import { AddGeneSetUploadTab } from "./AddGeneSetUploadTab";

interface AddGeneSetModalProps {
  open: boolean;
  onClose: () => void;
}

type Tab = "paste" | "upload";

const TABS: { value: Tab; label: string }[] = [
  { value: "paste", label: "Paste IDs" },
  { value: "upload", label: "Upload File" },
];

export function AddGeneSetModal({ open, onClose }: AddGeneSetModalProps) {
  const [activeTab, setActiveTab] = useState<Tab>("paste");

  const handleClose = useCallback(() => {
    setActiveTab("paste");
    onClose();
  }, [onClose]);

  const handleCreated = useCallback(() => {
    setActiveTab("paste");
    onClose();
  }, [onClose]);

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Add Gene Set"
      maxWidth="max-w-lg"
      showCloseButton
    >
      <div className="p-5">
        <h2 className="text-base font-semibold text-foreground">Add Gene Set</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Import a list of gene IDs to analyse in the workbench.
        </p>

        {/* Tab switcher */}
        <div className="mt-4 flex rounded-lg bg-muted p-1">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              className={cn(
                "flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors duration-150",
                activeTab === tab.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="mt-4">
          {activeTab === "paste" && (
            <AddGeneSetPasteTab onClose={handleClose} onCreated={handleCreated} />
          )}
          {activeTab === "upload" && (
            <AddGeneSetUploadTab onClose={handleClose} onCreated={handleCreated} />
          )}
        </div>
      </div>
    </Modal>
  );
}
