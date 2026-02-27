import { useEffect } from "react";
import { applySiteTheme } from "@/features/sites/siteTheme";

/**
 * Applies the selected site's brand color to the document root whenever the
 * site ID changes.
 */
export function useSiteTheme(siteId: string): void {
  useEffect(() => {
    if (siteId) applySiteTheme(siteId);
  }, [siteId]);
}
