"use client";

import Image from "next/image";
import { getSiteBanner } from "@/features/sites/siteBanners";
import { SiteIcon } from "@/features/sites/components/SiteIcon";
import { SitePicker } from "@/features/sites/components/SitePicker";

interface TopBarProps {
  selectedSite: string;
  onSiteChange: (siteId: string) => void;
  /** Optional right-side actions (settings gear, nav links, etc.). */
  actions?: React.ReactNode;
}

/**
 * Application header bar with per-site VEuPathDB banner. Always uses a dark
 * overlay and white text/controls for readability.
 */
export function TopBar({ selectedSite, onSiteChange, actions }: TopBarProps) {
  const banner = getSiteBanner(selectedSite);

  return (
    <header
      className="relative min-h-[52px] border-b border-border shadow-sm"
      style={{
        backgroundImage: `url(${banner.imagePath})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      {/* Dark overlay so text and controls stay readable on every banner */}
      <div
        className="absolute inset-0 bg-gradient-to-r from-black/50 via-black/30 to-transparent"
        aria-hidden
      />
      <div className="relative flex items-center justify-between px-5 py-2.5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <Image
              src="/pathfinder-white.svg"
              alt="PathFinder"
              width={28}
              height={28}
              className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]"
            />
            <div>
              <div className="text-sm font-semibold tracking-tight text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]">
                PathFinder
              </div>
              <div className="text-[10px] font-medium uppercase tracking-wider text-white/90 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]">
                VEuPathDB Strategy Builder
              </div>
            </div>
          </div>

          <div className="mx-1 h-6 w-px bg-white/50" />

          <div className="flex items-center gap-2">
            <SiteIcon siteId={selectedSite} size={22} />
            <SitePicker
              value={selectedSite}
              onChange={onSiteChange}
              showSelect
              showVisit={false}
              showAuth={false}
              layout="inline"
              headerTextVariant="light"
            />
          </div>
        </div>
        <div className="flex items-center gap-3 [&_a]:text-white [&_a]:drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)] [&_a:hover]:!text-primary [&_a:hover]:drop-shadow-none [&_button]:text-white [&_button]:drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)] [&_button:hover]:!text-primary [&_button:hover]:drop-shadow-none [&_div.w-px]:bg-white/50">
          {actions}
          <SitePicker
            value={selectedSite}
            onChange={onSiteChange}
            showSelect={false}
            showVisit={false}
            showAuth
            layout="inline"
            headerTextVariant="light"
          />
        </div>
      </div>
    </header>
  );
}
