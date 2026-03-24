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
    badgeClass: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
  },
  paste: {
    icon: ClipboardPaste,
    label: "Paste",
    badgeClass:
      "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
  },
  upload: {
    icon: Upload,
    label: "Upload",
    badgeClass:
      "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
  },
  derived: {
    icon: GitMerge,
    label: "Derived",
    badgeClass:
      "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  },
  saved: {
    icon: Bookmark,
    label: "Saved",
    badgeClass:
      "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20",
  },
};
