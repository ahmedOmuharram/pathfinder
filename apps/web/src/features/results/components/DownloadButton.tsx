"use client";

import { useState } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Download, Loader2 } from "lucide-react";

interface DownloadButtonProps {
  onDownload: (format: string) => Promise<string>;
  disabled?: boolean;
}

const FORMATS = [
  { id: "csv", label: "CSV" },
  { id: "tab", label: "Tab-delimited" },
  { id: "json", label: "JSON" },
];

export function DownloadButton({ onDownload, disabled }: DownloadButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async (format: string) => {
    setLoading(true);
    setError(null);
    try {
      const url = await onDownload(format);
      window.open(url, "_blank");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Download failed. Please try again.";
      setError(message);
      console.error("Download failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative">
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            disabled={disabled || loading}
            className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-900 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Download
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            className="z-50 min-w-[180px] rounded-md border border-slate-200 bg-white p-1 shadow-lg"
            sideOffset={4}
            align="end"
          >
            {FORMATS.map((format) => (
              <DropdownMenu.Item
                key={format.id}
                onSelect={() => handleDownload(format.id)}
                className="flex w-full cursor-pointer items-center gap-2 rounded px-3 py-2 text-left text-[12px] text-slate-700 outline-none transition-colors hover:bg-slate-50 focus:bg-slate-50"
              >
                {format.label}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      {error && <div className="mt-1 text-[11px] text-red-600">{error}</div>}
    </div>
  );
}
