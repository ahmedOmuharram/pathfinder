import { useQuery } from "@tanstack/react-query";
import { geneSetsListOptions } from "@/features/workbench/api/geneSets";
import { useSessionStore } from "@/state/useSessionStore";

export function useGeneSetsQuery(siteId: string) {
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const authStatusKnown = useSessionStore((s) => s.authStatusKnown);

  return useQuery({
    ...geneSetsListOptions(siteId),
    enabled: authStatusKnown && veupathdbSignedIn && siteId !== "",
  });
}
