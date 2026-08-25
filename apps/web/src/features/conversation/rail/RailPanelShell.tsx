"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useRightRailStore } from "@/state/useRightRailStore";

interface RailPanelShellProps {
  title: string;
  children: React.ReactNode;
  headerActions?: React.ReactNode;
}

export function RailPanelShell({
  title,
  children,
  headerActions,
}: RailPanelShellProps) {
  const close = useRightRailStore((s) => s.closePanel);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="text-sm font-semibold text-foreground">{title}</span>
        <div className="flex items-center gap-1">
          {headerActions}
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={close}
            aria-label={`Close ${title}`}
          >
            <X className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      </div>
      {/* A rail panel can hold read-only text, so the scroller carries its own
          tab stop; without one the keyboard cannot reach the overflow. */}
      <div
        className="min-h-0 flex-1 overflow-auto"
        role="region"
        aria-label={`${title} detail`}
        tabIndex={0}
      >
        {children}
      </div>
    </div>
  );
}

interface RailEmptyStateProps {
  icon: React.ReactNode;
  heading: string;
  description: string;
}

export function RailEmptyState({ icon, heading, description }: RailEmptyStateProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
      <div className="text-muted-foreground">{icon}</div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{heading}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
