"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export interface SectionProps {
  title: string;
  description?: string;
  defaultOpen?: boolean;
  collapsible?: boolean;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
}

export function Section({
  title,
  description,
  defaultOpen = true,
  collapsible = true,
  children,
  className,
  actions,
}: SectionProps) {
  const [open, setOpen] = React.useState(defaultOpen);

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {collapsible && (
            <button
              type="button"
              onClick={() => setOpen(!open)}
              className="flex h-5 w-5 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <ChevronDown
                className={cn(
                  "h-4 w-4 transition-transform duration-200",
                  !open && "-rotate-90",
                )}
              />
            </button>
          )}
          <div>
            <h3 className="text-sm font-semibold leading-none">{title}</h3>
            {description && (
              <p className="mt-1 text-xs text-muted-foreground">{description}</p>
            )}
          </div>
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      {open && <div className="animate-fade-in">{children}</div>}
    </div>
  );
}
