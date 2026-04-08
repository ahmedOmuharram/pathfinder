"use client";

import { Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { controlSetsOptions } from "../api/controlSets";

interface ControlSetQuickPickProps {
  siteId: string;
  onSelect: (positiveIds: string[], negativeIds: string[]) => void;
}

export function ControlSetQuickPick({ siteId, onSelect }: ControlSetQuickPickProps) {
  const { data: controlSets, isPending } = useQuery(controlSetsOptions(siteId));

  if (isPending) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading control sets...
      </div>
    );
  }

  if (controlSets == null || controlSets.length === 0) {
    return <p className="text-xs text-muted-foreground">No saved control sets</p>;
  }

  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-muted-foreground">
        Quick pick from saved controls
      </p>
      <div className="flex flex-col gap-0.5">
        {controlSets.map((cs) => (
          <button
            key={cs.id}
            type="button"
            className="flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-xs hover:bg-accent text-left"
            onClick={() => onSelect(cs.positiveIds, cs.negativeIds)}
          >
            <span>{cs.name}</span>
            <span className="text-muted-foreground text-[10px]">
              {cs.positiveIds.length}+ / {cs.negativeIds.length}−
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
