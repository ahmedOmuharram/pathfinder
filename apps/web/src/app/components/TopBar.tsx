"use client";

import Image from "next/image";
import { SitePicker } from "@/features/sites/components/SitePicker";

interface TopBarProps {
  selectedSite: string;
  onSiteChange: (siteId: string) => void;
  /** Optional right-side actions (settings gear, nav links, etc.). */
  actions?: React.ReactNode;
}

/**
 * Application header bar with logo, site picker, and action slots.
 */
export function TopBar({ selectedSite, onSiteChange, actions }: TopBarProps) {
  return (
    <header className="border-b border-border bg-card shadow-xs">
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-3">
          <Image src="/pathfinder.svg" alt="PathFinder" width={32} height={32} />
          <div>
            <div className="text-sm font-semibold tracking-tight text-foreground">
              PathFinder
            </div>
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              VEuPathDB Strategy Builder
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <SitePicker
            value={selectedSite}
            onChange={onSiteChange}
            showSelect={false}
            showVisit={false}
            showAuth
            layout="inline"
          />
          {actions}
        </div>
      </div>
    </header>
  );
}
