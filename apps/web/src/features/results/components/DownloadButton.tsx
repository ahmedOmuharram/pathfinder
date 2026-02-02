"use client";

import { useState } from "react";

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
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleDownload = async (format: string) => {
    setLoading(true);
    try {
      const url = await onDownload(format);
      // Open download URL
      window.open(url, "_blank");
    } catch (error) {
      console.error("Download failed:", error);
    } finally {
      setLoading(false);
      setIsOpen(false);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled || loading}
        className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-900 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? (
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
            <circle
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
              opacity={0.25}
            />
            <path
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        ) : (
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            className="h-4 w-4"
          >
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
          </svg>
        )}
        Download
        <svg
          className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 z-10 mt-2 w-48 rounded-md border border-slate-200 bg-white shadow-lg">
          {FORMATS.map((format) => (
            <button
              key={format.id}
              onClick={() => handleDownload(format.id)}
              className="flex w-full items-center gap-2 px-4 py-2 text-left text-[12px] text-slate-700 transition-colors hover:bg-slate-50 first:rounded-t-md last:rounded-b-md"
            >
              {format.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

