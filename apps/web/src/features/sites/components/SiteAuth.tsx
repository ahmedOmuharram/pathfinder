"use client";

import { useEffect, useState } from "react";
import { getVeupathdbAuthStatus, logoutVeupathdb } from "@/lib/api/veupathdb-auth";
import { useSessionStore } from "@/state/useSessionStore";
import { Modal } from "@/lib/components/Modal";
import { SignInForm } from "@/features/sites/components/SignInForm";
import type { HeaderTextVariant } from "@/features/sites/siteBanners";
import { cn } from "@/lib/utils/cn";

interface SiteAuthProps {
  siteId: string;
  /** When "inline", show sign-in form directly. When "button", show "Sign in →" that opens a modal. */
  authDisplay?: "button" | "inline";
  /** When in header with banner, use "light" for white text + shadow. */
  headerTextVariant?: HeaderTextVariant;
}

export function SiteAuth({
  siteId,
  authDisplay = "button",
  headerTextVariant,
}: SiteAuthProps) {
  const [authStatus, setAuthStatus] = useState<{
    signedIn: boolean;
    name?: string | null;
  } | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);

  const veupathdbSignedIn = useSessionStore((state) => state.veupathdbSignedIn);
  const veupathdbName = useSessionStore((state) => state.veupathdbName);
  const setVeupathdbAuth = useSessionStore((state) => state.setVeupathdbAuth);

  const displaySignedIn = veupathdbSignedIn === true || authStatus?.signedIn === true;
  const displayName = veupathdbName ?? authStatus?.name ?? "";

  useEffect(() => {
    if (siteId === "") return;
    getVeupathdbAuthStatus(siteId)
      .then((status) => {
        setAuthStatus(status);
        setVeupathdbAuth(status.signedIn, status.name ?? null);
      })
      .catch((err) => {
        console.warn("[SiteAuth] Failed to check auth status:", err);
        setAuthStatus({ signedIn: false });
        setVeupathdbAuth(false, null);
      });
  }, [siteId, setVeupathdbAuth]);

  const lightClass =
    "text-white/95 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)] transition-colors duration-150 hover:text-primary hover:drop-shadow-none";
  const darkClass = "text-muted-foreground transition-colors duration-150 hover:text-foreground";
  const actionClass = headerTextVariant === "light" ? lightClass : darkClass;

  return (
    <>
      {displaySignedIn && (
        <div className={cn("flex items-center gap-3 text-xs")}>
          <span
            className={
              headerTextVariant === "light"
                ? "text-white/95 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]"
                : "text-muted-foreground"
            }
          >
            Logged in as {displayName !== "" ? displayName : "—"}
          </span>
          <button
            type="button"
            onClick={() => {
              void (async () => {
                try {
                  await logoutVeupathdb(siteId);
                  setAuthStatus({ signedIn: false });
                  setVeupathdbAuth(false, null);
                } catch {
                  console.warn("[SiteAuth] Failed to log out");
                }
              })();
            }}
            className={actionClass}
          >
            Log out
          </button>
        </div>
      )}

      {authDisplay === "button" && !displaySignedIn && (
        <button
          type="button"
          onClick={() => setShowLoginModal(true)}
          className={cn("text-xs", actionClass)}
        >
          Sign in →
        </button>
      )}

      {authDisplay === "inline" && !displaySignedIn && (
        <div className="mt-4">
          <SignInForm onSuccess={() => setAuthStatus({ signedIn: true })} />
        </div>
      )}

      <Modal
        open={showLoginModal}
        onClose={() => setShowLoginModal(false)}
        title="Sign in to VEuPathDB"
        maxWidth="max-w-sm"
        showCloseButton
      >
        <div className="p-5">
          <SignInForm
            onSuccess={() => {
              setShowLoginModal(false);
              setAuthStatus({ signedIn: true });
            }}
          />
        </div>
      </Modal>
    </>
  );
}
