"use client";

import { Loader2 } from "lucide-react";
import { useParamSpecs } from "@/lib/hooks/useParamSpecs";

interface ParamNameSelectProps {
  siteId: string;
  recordType: string;
  searchName: string;
  value: string | null;
  onChange: (paramName: string) => void;
  placeholder?: string;
}

export function ParamNameSelect({
  siteId,
  recordType,
  searchName,
  value,
  onChange,
  placeholder,
}: ParamNameSelectProps) {
  const { paramSpecs, isLoading } = useParamSpecs(siteId, recordType, searchName);

  if (isLoading) {
    return (
      <div className="flex h-8 items-center rounded-md border border-input bg-background px-2.5 text-xs text-muted-foreground">
        <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
        Loading parameters…
      </div>
    );
  }

  if (paramSpecs.length === 0) {
    return (
      <div className="flex h-8 items-center rounded-md border border-input bg-background px-2.5 text-xs text-muted-foreground">
        No parameters available
      </div>
    );
  }

  return (
    <select
      className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      value={value ?? ""}
      onChange={(e) => {
        if (e.target.value) {
          onChange(e.target.value);
        }
      }}
    >
      <option value="">{placeholder ?? "Select parameter..."}</option>
      {paramSpecs.map((s) => (
        <option key={s.name} value={s.name}>
          {s.displayName != null && s.displayName !== "" ? s.displayName : s.name}
        </option>
      ))}
    </select>
  );
}
