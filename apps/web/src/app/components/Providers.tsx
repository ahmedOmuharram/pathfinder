"use client";

import { TooltipProvider } from "@/lib/components/ui/Tooltip";
import { QueryProvider } from "@/lib/query/QueryProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
    </QueryProvider>
  );
}
