"use client";

import { useRef } from "react";
import { FileUp } from "lucide-react";

import { parseGeneCsv } from "@/lib/utils/parseGeneCsv";

interface CsvImportButtonProps {
  onImport: (geneIds: string[]) => void;
}

export function CsvImportButton({ onImport }: CsvImportButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result as string;
      const ids = parseGeneCsv(text);
      if (ids.length > 0) onImport(ids);
    };
    reader.readAsText(file);

    // Reset so same file can be re-selected
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="inline-flex items-center gap-1.5 rounded-md border border-input px-2.5 py-1 text-xs text-muted-foreground transition-colors duration-150 hover:border-foreground/30 hover:text-foreground"
      >
        <FileUp className="h-3 w-3" />
        Import
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.tsv,.txt"
        onChange={handleChange}
        className="hidden"
      />
    </>
  );
}
