"use client";

import { useState } from "react";
import { useSuspenseQuery, useQueryClient } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";
import { authStatusOptions } from "@/lib/api/veupathdb-auth";
import { invalidateUserScopedQueries } from "@/lib/query/invalidateUserScoped";
import { useSessionStore } from "@/state/useSessionStore";

export function useAuthCheck(): void {
  const queryClient = useQueryClient();
  const { setVeupathdbAuth, setAuthStatusKnown, selectedSite, bumpAuthVersion } =
    useSessionStore(
      useShallow((s) => ({
        setVeupathdbAuth: s.setVeupathdbAuth,
        setAuthStatusKnown: s.setAuthStatusKnown,
        selectedSite: s.selectedSite,
        bumpAuthVersion: s.bumpAuthVersion,
      })),
    );

  const { enabled: _enabled, ...opts } = authStatusOptions(selectedSite);
  const { data } = useSuspenseQuery(opts);

  const authKey = `${data.signedIn ? "1" : "0"}:${data.name ?? ""}`;
  const [prevAuthKey, setPrevAuthKey] = useState(authKey);
  const [prevSignedIn, setPrevSignedIn] = useState(data.signedIn);
  if (authKey !== prevAuthKey) {
    setPrevAuthKey(authKey);
    setPrevSignedIn(data.signedIn);
    setVeupathdbAuth(data.signedIn, data.name ?? null);
    setAuthStatusKnown(true);

    if (prevSignedIn !== data.signedIn) {
      queueMicrotask(() => {
        invalidateUserScopedQueries(queryClient);
        bumpAuthVersion();
      });
    }
  }

  const [initialized, setInitialized] = useState(false);
  if (!initialized) {
    setInitialized(true);
    setVeupathdbAuth(data.signedIn, data.name ?? null);
    setAuthStatusKnown(true);
  }
}
