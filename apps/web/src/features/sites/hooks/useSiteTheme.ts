import { useIsomorphicLayoutEffect } from "usehooks-ts";
import { applySiteTheme } from "@/features/sites/siteTheme";

/**
 * Applies the selected site's brand color to the document root whenever the
 * site ID changes.
 */
export function useSiteTheme(siteId: string): void {
  useIsomorphicLayoutEffect(() => {
    if (siteId) applySiteTheme(siteId);
  }, [siteId]);
}
