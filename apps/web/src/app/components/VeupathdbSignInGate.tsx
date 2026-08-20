"use client";

import { toast } from "sonner";

import { setQueryErrorHandler } from "@/lib/query/client";
import { handleWdkLoginRequired, useAuthGateStore } from "@/state/useAuthGateStore";
import { LoginModal } from "./LoginModal";

interface VeupathdbSignInGateProps {
  /** True while the session has no VEuPathDB login of its own. */
  forced: boolean;
  selectedSite: string;
  onSiteChange: (siteId: string) => void;
}

/**
 * The one sign-in prompt of an app shell. It also owns the query error
 * handler, so a route refused for want of a VEuPathDB login opens the prompt
 * from any shell that renders this.
 */
export function VeupathdbSignInGate({
  forced,
  selectedSite,
  onSiteChange,
}: VeupathdbSignInGateProps) {
  const signInRequired = useAuthGateStore((s) => s.signInRequired);
  const signInReason = useAuthGateStore((s) => s.signInReason);
  const dismissSignIn = useAuthGateStore((s) => s.dismissSignIn);

  setQueryErrorHandler((notice) => {
    if (handleWdkLoginRequired(notice.error)) return;
    toast.error(notice.message);
  });

  if (forced) {
    return <LoginModal open selectedSite={selectedSite} onSiteChange={onSiteChange} />;
  }

  return (
    <LoginModal
      open={signInRequired}
      reason={signInReason}
      selectedSite={selectedSite}
      onSiteChange={onSiteChange}
      onDismiss={dismissSignIn}
    />
  );
}
