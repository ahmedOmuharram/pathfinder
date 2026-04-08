import * as React from "react";
import { cn } from "@/lib/utils/cn";

function Card({ className, ref, ...props }: React.HTMLAttributes<HTMLDivElement> & { ref?: React.Ref<HTMLDivElement> }) {
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border bg-card text-card-foreground shadow-xs",
        className,
      )}
      {...props}
    />
  );
}

export { Card };
