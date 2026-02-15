"use client";

import Image from "next/image";
import { SitePicker } from "@/features/sites/components/SitePicker";

interface TopBarProps {
  selectedSite: string;
  onSiteChange: (siteId: string) => void;
  /** Optional right-side actions (settings gear, etc.). */
  actions?: React.ReactNode;
}

/**
 * Application header bar with logo and site picker.
 */
export function TopBar({ selectedSite, onSiteChange, actions }: TopBarProps) {
  return (
    <div className="border-b border-slate-200 bg-white px-5 py-3">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Image src="/pathfinder.svg" alt="PathFinder" width={32} height={32} />
          <div>
            <div className="text-base font-semibold tracking-tight text-slate-900">
              PathFinder
            </div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              VEuPathDB Strategy Builder
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
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
    </div>
  );
}
