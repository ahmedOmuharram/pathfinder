import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { sitesOptions } from "@/lib/api/sites";

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/service\/?$/, "").replace(/\/a\/?$/, "");
}

export function useWdkUrlFallback(args: {
  wdkStrategyId: number | null | undefined;
  siteId: string | undefined;
}): string | null {
  const { wdkStrategyId, siteId } = args;

  const { data: sites } = useQuery(sitesOptions());

  return useMemo(() => {
    if (wdkStrategyId == null || siteId == null || siteId === "" || sites == null) return null;
    const site = sites.find((s) => s.id === siteId);
    if (site?.baseUrl == null || site.baseUrl === "") return null;
    return `${normalizeBaseUrl(site.baseUrl)}/app/workspace/strategies/${wdkStrategyId}`;
  }, [wdkStrategyId, siteId, sites]);
}
