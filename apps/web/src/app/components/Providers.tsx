"use client";

import { TooltipProvider } from "@/lib/components/ui/Tooltip";

export function Providers({ children }: { children: React.ReactNode }) {
  return <TooltipProvider delayDuration={300}>{children}</TooltipProvider>;
}
