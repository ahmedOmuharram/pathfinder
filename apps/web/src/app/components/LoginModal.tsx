"use client";

import Image from "next/image";
import { Modal } from "@/lib/components/Modal";
import { SignInForm } from "@/features/sites/components/SignInForm";

interface LoginModalProps {
  open: boolean;
  selectedSite: string;
  onSiteChange: (siteId: string) => void;
}

/**
 * Forced sign-in modal overlay.
 *
 * Shown when the user is not authenticated. Cannot be dismissed until signed in.
 * Accepts VEuPathDB login only; no database/site selection.
 */
export function LoginModal({ open, onSiteChange }: LoginModalProps) {
  const handleSuccess = () => {
    onSiteChange("veupathdb");
  };

  return (
    <Modal
      open={open}
      onClose={() => {}}
      title="Sign in to VEuPathDB"
      maxWidth="max-w-md"
      dismissible={false}
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
            Sign in with your VEuPathDB account to build and manage search strategies.
          </p>
        </div>

        <div className="border-t border-border px-6 py-5">
          <SignInForm onSuccess={handleSuccess} />
        </div>
      </div>
    </Modal>
  );
}
