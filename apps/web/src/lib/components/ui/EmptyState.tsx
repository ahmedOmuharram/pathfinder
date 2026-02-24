import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  heading: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  heading,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div className={cn("flex h-full items-center justify-center", className)}>
      <div className="text-center max-w-sm animate-fade-in">
        {icon && (
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center text-muted-foreground">
            {icon}
          </div>
        )}
        <h2 className="text-base font-semibold text-foreground">{heading}</h2>
        {description && (
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
            {description}
          </p>
        )}
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  );
}
