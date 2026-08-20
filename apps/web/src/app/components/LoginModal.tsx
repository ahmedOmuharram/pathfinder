"use client";

import Image from "next/image";
import { Modal } from "@/lib/components/Modal";
import { SignInForm } from "@/features/sites/components/SignInForm";
import { useAuthGateStore } from "@/state/useAuthGateStore";

interface LoginModalProps {
  open: boolean;
  selectedSite: string;
  onSiteChange: (siteId: string) => void;
  /** The server's explanation, shown in place of the standing invitation. */
  reason?: string | null;
  /** Present only where the prompt may be closed again. */
  onDismiss?: () => void;
}

const STANDING_INVITATION =
  "Sign in with your VEuPathDB account to build and manage search strategies.";

/**
 * VEuPathDB sign-in overlay.
 *
 * Every WDK-backed feature needs a registered VEuPathDB login. Without
 * `onDismiss` the prompt cannot be closed until the user signs in.
 */
export function LoginModal({
  open,
  selectedSite,
  onSiteChange,
  reason,
  onDismiss,
}: LoginModalProps) {
  const dismissSignIn = useAuthGateStore((s) => s.dismissSignIn);
  const dismissible = onDismiss !== undefined;
  const handleSuccess = () => {
    dismissSignIn();
    // Preserve the user's current site selection after login.
    // Default to veupathdb only if no site was previously selected.
    onSiteChange(selectedSite || "veupathdb");
  };

  return (
    <Modal
      open={open}
      onClose={onDismiss ?? (() => {})}
      title="Sign in to VEuPathDB"
      maxWidth="max-w-md"
      dismissible={dismissible}
      showCloseButton={dismissible}
    >
      <div className="overflow-hidden rounded-xl">
        <div className="bg-gradient-to-br from-primary/10 via-primary/5 to-transparent px-6 pb-4 pt-6">
          <div className="flex items-center gap-3">
            <Image src="/pathfinder.svg" alt="" width={36} height={36} />
            <div>
              <div className="text-base font-semibold tracking-tight text-foreground">
                PathFinder
              </div>
              <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                VEuPathDB Strategy Builder
              </div>
            </div>
          </div>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            {reason != null && reason !== "" ? reason : STANDING_INVITATION}
          </p>
        </div>

        <div className="border-t border-border px-6 py-5">
          <SignInForm onSuccess={handleSuccess} />
        </div>
      </div>
    </Modal>
  );
}
