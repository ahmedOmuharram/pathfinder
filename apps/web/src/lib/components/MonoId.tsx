"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/Tooltip";
import { cn } from "@/lib/utils/cn";

/**
 * A monospace identifier (search name, param id, ...) that truncates to its
 * container with an ellipsis and reveals the full value on hover/focus —
 * so long WDK ids never force horizontal scroll in the rail.
 */
export function MonoId({ id, className }: { id: string; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <code
          className={cn(
            "block max-w-full cursor-default truncate font-mono",
            className,
          )}
        >
          {id}
        </code>
      </TooltipTrigger>
      <TooltipContent
        side="bottom"
        align="start"
        className="max-w-[min(90vw,28rem)] break-all font-mono"
      >
        {id}
      </TooltipContent>
    </Tooltip>
  );
}
