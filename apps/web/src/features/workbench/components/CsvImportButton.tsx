"use client";

import { useCallback, useRef } from "react";
import { FileUp } from "lucide-react";

interface CsvImportButtonProps {
  onImport: (geneIds: string[]) => void;
}

export function parseGeneIds(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => {
      // Split on comma or tab, take first column
      const first = line.split(/[,\t]/)[0] ?? "";
      return first.trim();
    })
    .filter((id) => id.length > 0 && !id.match(/^gene.?id$/i)); // skip headers
}

export function CsvImportButton({ onImport }: CsvImportButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = () => {
        const text = reader.result as string;
        const ids = parseGeneIds(text);
        if (ids.length > 0) onImport(ids);
      };
      reader.readAsText(file);

      // Reset so same file can be re-selected
      if (inputRef.current) inputRef.current.value = "";
    },
    [onImport],
  );

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
