"use client";

import { useQuery } from "@tanstack/react-query";
import { systemReadyQueryOptions } from "@pathfinder/shared/generated/hooks/useSystemReady";

import { StartupScreen } from "./StartupScreen";

export function SystemReadyGate({ children }: { children: React.ReactNode }) {
  const { data } = useQuery({
    ...systemReadyQueryOptions(),
    refetchInterval: (query) => (query.state.data?.ready === true ? false : 2000),
  });

  if (data?.ready !== true) return <StartupScreen notReady={data?.notReady ?? []} />;
  return <>{children}</>;
}
