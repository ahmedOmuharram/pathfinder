"use client";

import { cn } from "@/lib/utils/cn";

export type CornerDotVariant = "error" | "warning" | "unsaved";

interface CornerDotProps {
  variant: CornerDotVariant;
}

const STYLE: Record<CornerDotVariant, string> = {
  error: "bg-destructive ring-background",
  warning: "bg-warning ring-background",
  unsaved: "bg-destructive ring-background",
};

const LABEL: Record<CornerDotVariant, string> = {
  error: "Validation error",
  warning: "Validation warning",
  unsaved: "Unsaved changes",
};

export function CornerDot({ variant }: CornerDotProps) {
  return (
    <span
      data-corner-dot={variant}
      aria-label={LABEL[variant]}
      className={cn(
        "absolute -left-1 -top-1 z-10 h-2.5 w-2.5 rounded-full ring-2",
        STYLE[variant],
      )}
    />
  );
}
