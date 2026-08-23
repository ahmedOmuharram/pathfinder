"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { PrivacySettings } from "@pathfinder/shared";

import {
  getPrivacySettings,
  updatePrivacySettings,
} from "@/features/settings/api/privacy";
import { Modal } from "@/lib/components/Modal";

import { PRIVACY_QUERY_KEY } from "./settings/privacyQuery";

/**
 * The one-screen eval-data notice. Escape, the backdrop and either button all
 * record that the account has seen it, and the marker is server-side.
 */
export function EvalDataNotice() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: PRIVACY_QUERY_KEY,
    queryFn: getPrivacySettings,
    staleTime: Infinity,
    retry: false,
  });

  const acknowledge = useMutation({
    mutationFn: async (keepConsent: boolean) =>
      updatePrivacySettings(
        keepConsent
          ? { noticeSeen: true }
          : { noticeSeen: true, evalDataConsent: false },
      ),
    onSuccess: (next: PrivacySettings) => {
      qc.setQueryData(PRIVACY_QUERY_KEY, next);
    },
  });

  const open = data != null && !data.noticeSeen && !acknowledge.isPending;

  return (
    <Modal
      open={open}
      onClose={() => acknowledge.mutate(true)}
      title="How PathFinder learns"
      maxWidth="max-w-lg"
    >
      <div className="space-y-4 p-6">
        <h2 className="text-base font-semibold text-foreground">
          How PathFinder learns
        </h2>
        <p className="text-sm leading-relaxed text-muted-foreground">
          PathFinder improves by learning from real strategies. We keep the science,
          never your identity. You can turn this off anytime in Settings.
        </p>
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => acknowledge.mutate(false)}
            className="text-sm font-medium text-muted-foreground underline underline-offset-4 hover:text-foreground"
          >
            Turn off
          </button>
          <button
            type="button"
            onClick={() => acknowledge.mutate(true)}
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            OK
          </button>
        </div>
      </div>
    </Modal>
  );
}
