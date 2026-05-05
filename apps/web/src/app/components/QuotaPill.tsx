"use client";

import { useQuery } from "@tanstack/react-query";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { getMyQuotaQueryOptions } from "@pathfinder/shared/generated/hooks/useGetMyQuota";
import { cn } from "@/lib/utils/cn";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const currencySubCent = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

function formatUsed(value: number): string {
  if (value <= 0) return currency.format(0);
  if (value < 0.01) return currencySubCent.format(value);
  return currency.format(value);
}

const compact = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

function formatResetsAt(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function QuotaPill() {
  const { data } = useQuery(getMyQuotaQueryOptions());
  if (data == null) return null;

  const used = Number(data.usedUsd);
  const limit = Number(data.limitUsd);
  const pct = limit > 0 ? Math.min(used / limit, 1) : 0;

  const tone =
    pct >= 1
      ? "bg-red-500/25 text-red-50 ring-1 ring-red-300/60"
      : pct >= 0.8
        ? "bg-amber-400/25 text-amber-50 ring-1 ring-amber-200/60"
        : "bg-white/15 text-white ring-1 ring-white/30";

  const barColor = pct >= 1 ? "bg-red-300" : pct >= 0.8 ? "bg-amber-200" : "bg-white/80";

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            aria-label="Monthly quota"
            className={cn(
              "flex items-center gap-2 rounded-full px-2.5 py-1 text-[11px] font-medium drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]",
              tone,
            )}
          >
            <span>
              {formatUsed(used)} / {currency.format(limit)}
            </span>
            <span className="h-1 w-12 overflow-hidden rounded-full bg-black/30">
              <span
                className={cn("block h-full transition-[width]", barColor)}
                style={{ width: `${Math.max(pct * 100, 2)}%` }}
              />
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          {compact.format(data.totalTokens)} tokens · resets {formatResetsAt(data.resetsAt)}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
