"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert } from "lucide-react";

import { userQuotaOptions } from "@/lib/api/quota";

const dateFmt = new Intl.DateTimeFormat("en-US", {
  month: "long",
  day: "numeric",
  year: "numeric",
});

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function QuotaExhaustedBanner() {
  const { data } = useQuery(userQuotaOptions());
  if (data == null) return null;
  const used = Number(data.usedUsd);
  const limit = Number(data.limitUsd);
  if (limit <= 0 || used < limit) return null;

  return (
    <div
      role="alert"
      data-testid="quota-exhausted-banner"
      className="mx-auto flex w-full max-w-3xl items-start gap-3 border-t border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">Monthly quota reached</p>
        <p className="mt-0.5 text-xs text-destructive/80">
          You&apos;ve used {currency.format(used)} of your{" "}
          {currency.format(limit)} monthly limit. New messages are paused
          until {dateFmt.format(new Date(data.resetsAt))}.
        </p>
      </div>
    </div>
  );
}

export function useQuotaExhausted(): boolean {
  const { data } = useQuery(userQuotaOptions());
  if (data == null) return false;
  const used = Number(data.usedUsd);
  const limit = Number(data.limitUsd);
  return limit > 0 && used >= limit;
}
