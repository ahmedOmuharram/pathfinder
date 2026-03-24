"use client";

import { useEffect, useState } from "react";
import { listSites } from "@/lib/api/sites";
import { VEUPATHDB_SITES } from "@pathfinder/shared";
import type { VEuPathDBSite } from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { Label } from "@/lib/components/ui/Label";
import { cn } from "@/lib/utils/cn";
import type { HeaderTextVariant } from "@/features/sites/siteBanners";

interface SitePickerProps {
  value: string;
  onChange: (siteId: string) => void;
  /** When in header with banner, use "light" for white text + shadow. */
  headerTextVariant?: HeaderTextVariant;
}

export function SitePicker({
  value,
  onChange,
  headerTextVariant,
}: SitePickerProps) {
  const [sites, setSites] = useState<VEuPathDBSite[]>(VEUPATHDB_SITES);
  const [loading, setLoading] = useState(true);
  const setSelectedSiteInfo = useSessionStore((state) => state.setSelectedSiteInfo);

  useEffect(() => {
    listSites()
      .then(setSites)
      .catch((err) => {
        console.warn("[SitePicker] Failed to load sites, using fallback:", err);
        setSites(VEUPATHDB_SITES);
      })
      .finally(() => setLoading(false));
  }, []);

  const selectedSite = sites.find((s) => s.id === value);

  useEffect(() => {
    if (selectedSite) {
      setSelectedSiteInfo(
        selectedSite.id,
        selectedSite.displayName !== "" ? selectedSite.displayName : selectedSite.name,
      );
    }
  }, [selectedSite, setSelectedSiteInfo]);

  return (
    <div data-testid="site-picker" className="flex items-center gap-3">
      <Label
        className={cn(
          "text-xs uppercase tracking-wide",
          headerTextVariant === "light"
            ? "text-white/90 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]"
            : "text-muted-foreground",
        )}
      >
        Database:
      </Label>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={loading}
          data-testid="site-select"
          className={cn(
            "appearance-none rounded-md border pr-8 px-3 py-1.5 text-sm shadow-xs transition-colors focus:outline-none focus:ring-2",
            headerTextVariant === "light"
              ? "border-white/40 bg-white/15 text-white focus:border-white/60 focus:ring-white/30 [&_option]:bg-background [&_option]:text-foreground"
              : "border-border bg-background text-foreground hover:border-input focus:border-primary focus:ring-primary/20",
          )}
        >
          <optgroup label="Component Sites">
            {sites
              .filter((s) => !s.isPortal)
              .map((site) => (
                <option key={site.id} value={site.id}>
                  {site.displayName}
                </option>
              ))}
          </optgroup>
          <optgroup label="Portal">
            {sites
              .filter((s) => s.isPortal)
              .map((site) => (
                <option key={site.id} value={site.id}>
                  {site.displayName}
                </option>
              ))}
          </optgroup>
        </select>
        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
          <svg
            className={cn(
              "h-4 w-4",
              headerTextVariant === "light"
                ? "text-white/80"
                : "text-muted-foreground",
            )}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </div>
    </div>
  );
}
