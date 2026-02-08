import { useEffect, useRef, useState } from "react";

export type SiteSummary = { id: string; baseUrl?: string | null };

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/service\/?$/, "").replace(/\/a\/?$/, "");
}

export function useWdkUrlFallback(args: {
  wdkStrategyId: number | undefined;
  siteId: string | undefined;
  listSites: () => Promise<SiteSummary[]>;
}): string | null {
  const { wdkStrategyId, siteId, listSites } = args;
  const [fallback, setFallback] = useState<string | null>(null);
  const siteBaseUrlCacheRef = useRef<Record<string, string>>({});

  useEffect(() => {
    if (!wdkStrategyId || !siteId) {
      setFallback(null);
      return;
    }

    let isActive = true;

    const cachedBaseUrl = siteBaseUrlCacheRef.current[siteId];
    if (cachedBaseUrl) {
      const url = normalizeBaseUrl(cachedBaseUrl);
      setFallback(`${url}/app/workspace/strategies/${wdkStrategyId}`);
      return;
    }

    listSites()
      .then((sites) => {
        if (!isActive) return;
        const match = sites.find((site) => site.id === siteId);
        if (!match?.baseUrl) return;
        siteBaseUrlCacheRef.current[siteId] = match.baseUrl;
        const url = normalizeBaseUrl(match.baseUrl);
        setFallback(`${url}/app/workspace/strategies/${wdkStrategyId}`);
      })
      .catch(() => {
        if (!isActive) return;
        setFallback(null);
      });

    return () => {
      isActive = false;
    };
  }, [wdkStrategyId, siteId, listSites]);

  return fallback;
}
