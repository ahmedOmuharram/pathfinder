"use client";

import { useCallback, useEffect, useState } from "react";
import { getSystemConfig } from "@/lib/api/health";

/**
 * Checks whether the backend has at least one LLM provider configured.
 *
 * Runs once on mount. When `setupRequired` is true the app should show
 * a blocking screen instead of the login form — there is no point
 * authenticating if the system cannot serve chat requests.
 */
export function useSystemConfig(): {
  configLoading: boolean;
  setupRequired: boolean;
  retry: () => void;
} {
  const [configLoading, setConfigLoading] = useState(true);
  const [setupRequired, setSetupRequired] = useState(false);

  const check = useCallback(() => {
    setConfigLoading(true);
    getSystemConfig()
      .then((cfg) => {
        setSetupRequired(!cfg.llmConfigured);
      })
      .catch(() => {
        // If the endpoint is unreachable, don't block on setup screen —
        // the auth check will surface the API-down error instead.
        setSetupRequired(false);
      })
      .finally(() => {
        setConfigLoading(false);
      });
  }, []);

  useEffect(() => {
    const id = setTimeout(check, 0);
    return () => clearTimeout(id);
  }, [check]);

  return { configLoading, setupRequired, retry: check };
}
