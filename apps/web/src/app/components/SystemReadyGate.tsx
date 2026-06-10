"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useInterval } from "usehooks-ts";
import { systemReadyQueryOptions } from "@pathfinder/shared/generated/hooks/useSystemReady";

import { StartupScreen, startupStatus } from "./StartupScreen";

const STARTUP_GRACE_MS = 20_000;

export function SystemReadyGate({ children }: { children: React.ReactNode }) {
  const [mountedAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());
  const { data, isError } = useQuery({
    ...systemReadyQueryOptions(),
    retry: false,
    refetchInterval: (query) => (query.state.data?.ready === true ? false : 2000),
  });

  const ready = data?.ready === true;
  // Heartbeat so the grace window can elapse even if a readiness request is
  // stuck in-flight (e.g. the DB is unreachable and the query never resolves).
  useInterval(() => setNow(Date.now()), ready ? null : 1000);

  if (ready) return <>{children}</>;

  const status = startupStatus({
    data,
    isError,
    elapsedMs: now - mountedAt,
    graceMs: STARTUP_GRACE_MS,
  });

  return <StartupScreen status={status} />;
}
