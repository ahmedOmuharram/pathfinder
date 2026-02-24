"use client";

import Image from "next/image";
import { SitePicker } from "@/features/sites/components/SitePicker";

interface LoginGateProps {
  selectedSite: string;
  onSiteChange: (siteId: string) => void;
}

/**
 * Full-screen login gate shown when the user hasn't authenticated with VEuPathDB.
 */
export function LoginGate({ selectedSite, onSiteChange }: LoginGateProps) {
  return (
    <div className="flex h-full flex-col bg-muted text-foreground">
      <div className="border-b border-border bg-card px-5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Image src="/pathfinder.svg" alt="PathFinder" width={32} height={32} />
            <div>
              <div className="text-base font-semibold tracking-tight text-foreground">
                PathFinder
              </div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">
                VEuPathDB Strategy Builder
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="flex flex-1 items-center justify-center">
        <div className="w-full max-w-sm rounded-lg border border-border bg-card p-8 shadow-sm">
          <h2 className="text-lg font-semibold text-foreground">Sign in to continue</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Please sign in with your VEuPathDB account to use PathFinder. Your
            strategies and plans will be saved to your account.
          </p>
          <div className="mt-6">
            <SitePicker
              value={selectedSite}
              onChange={onSiteChange}
              showSelect={false}
              showVisit={false}
              showAuth
              layout="stacked"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
