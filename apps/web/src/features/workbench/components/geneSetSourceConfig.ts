import { Database, ClipboardPaste, Upload, GitMerge, Bookmark } from "lucide-react";
import type { GeneSet } from "@pathfinder/shared";

interface SourceConfig {
  icon: React.ElementType;
  label: string;
  /** Tailwind classes for the badge (bg + text + border). */
  badgeClass: string;
}

export const SOURCE_CONFIG: Record<GeneSet["source"], SourceConfig> = {
  strategy: {
    icon: Database,
    label: "Strategy",
    badgeClass:
      "bg-[hsl(var(--chart-1)/0.1)] text-[hsl(var(--chart-1))] border-[hsl(var(--chart-1)/0.2)]",
  },
  paste: {
    icon: ClipboardPaste,
    label: "Paste",
    badgeClass:
      "bg-[hsl(var(--chart-3)/0.1)] text-[hsl(var(--chart-3))] border-[hsl(var(--chart-3)/0.2)]",
  },
  upload: {
    icon: Upload,
    label: "Upload",
    badgeClass:
      "bg-[hsl(var(--chart-5)/0.1)] text-[hsl(var(--chart-5))] border-[hsl(var(--chart-5)/0.2)]",
  },
  derived: {
    icon: GitMerge,
    label: "Derived",
    badgeClass:
      "bg-[hsl(var(--chart-2)/0.1)] text-[hsl(var(--chart-2))] border-[hsl(var(--chart-2)/0.2)]",
  },
  saved: {
    icon: Bookmark,
    label: "Saved",
    badgeClass: "bg-muted text-muted-foreground border-border",
  },
};
