"use client";

import { useEffect, useState } from "react";
import { getVeupathdbAuthStatus, listSites, logoutVeupathdb } from "@/lib/api/client";
import type { VEuPathDBSite as Site } from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { Modal } from "@/lib/components/Modal";
import { SignInForm } from "@/features/sites/components/SignInForm";
import type { HeaderTextVariant } from "@/features/sites/siteBanners";
import { cn } from "@/lib/utils/cn";

interface SitePickerProps {
  value: string;
  onChange: (siteId: string) => void;
  showSelect?: boolean;
  showAuth?: boolean;
  showVisit?: boolean;
  layout?: "inline" | "stacked";
  /** When "inline", show sign-in form directly. When "button", show "Sign in →" that opens a modal. */
  authDisplay?: "button" | "inline";
  /** When in header with banner, use "light" for white text + shadow or "dark" for default. */
  headerTextVariant?: HeaderTextVariant;
}

const FALLBACK_SITES: Site[] = [
  {
    id: "plasmodb",
    name: "PlasmoDB",
    displayName: "PlasmoDB",
    baseUrl: "https://plasmodb.org",
    projectId: "PlasmoDB",
    isPortal: false,
  },
  {
    id: "toxodb",
    name: "ToxoDB",
    displayName: "ToxoDB",
    baseUrl: "https://toxodb.org",
    projectId: "ToxoDB",
    isPortal: false,
  },
  {
    id: "cryptodb",
    name: "CryptoDB",
    displayName: "CryptoDB",
    baseUrl: "https://cryptodb.org",
    projectId: "CryptoDB",
    isPortal: false,
  },
  {
    id: "veupathdb",
    name: "VEuPathDB",
    displayName: "VEuPathDB Portal",
    baseUrl: "https://veupathdb.org",
    projectId: "EuPathDB",
    isPortal: true,
  },
];

const headerLightClasses =
  "text-white/95 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)] [&_a]:text-white/95 [&_a:hover]:!text-primary [&_a:hover]:drop-shadow-none [&_button]:text-white/95 [&_button:hover]:!text-primary [&_button:hover]:drop-shadow-none [&_span]:text-white/95 [&_span]:drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]";

export function SitePicker({
  value,
  onChange,
  showSelect = true,
  showAuth = true,
  showVisit = true,
  layout = "inline",
  authDisplay = "button",
  headerTextVariant,
}: SitePickerProps) {
  const headerClass = headerTextVariant === "light" ? headerLightClasses : "";
  const [sites, setSites] = useState<Site[]>(FALLBACK_SITES);
  const [loading, setLoading] = useState(true);
  const [authStatus, setAuthStatus] = useState<{
    signedIn: boolean;
    name?: string | null;
  } | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const veupathdbSignedIn = useSessionStore((state) => state.veupathdbSignedIn);
  const veupathdbName = useSessionStore((state) => state.veupathdbName);
  const setVeupathdbAuth = useSessionStore((state) => state.setVeupathdbAuth);
  const setAuthToken = useSessionStore((state) => state.setAuthToken);
  const setSelectedSiteInfo = useSessionStore((state) => state.setSelectedSiteInfo);

  const displaySignedIn = veupathdbSignedIn || !!authStatus?.signedIn;
  const displayName = veupathdbName ?? authStatus?.name ?? "";

  useEffect(() => {
    listSites()
      .then(setSites)
      .catch((err) => {
        console.warn("[SitePicker] Failed to load sites, using fallback:", err);
        setSites(FALLBACK_SITES);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!value) return;
    setAuthError(null);
    getVeupathdbAuthStatus()
      .then((status) => {
        setAuthStatus(status);
        setVeupathdbAuth(status.signedIn, status.name ?? null);
      })
      .catch((err) => {
        console.warn("[SitePicker] Failed to check auth status:", err);
        setAuthStatus({ signedIn: false });
        setVeupathdbAuth(false, null);
      })
      .finally(() => undefined);
  }, [value, setVeupathdbAuth]);

  const selectedSite = sites.find((s) => s.id === value);
  const visitUrl = selectedSite?.baseUrl
    ? (() => {
        try {
          return new URL(selectedSite.baseUrl).origin;
        } catch {
          return selectedSite.baseUrl.split("/").slice(0, 3).join("/");
        }
      })()
    : null;

  useEffect(() => {
    if (selectedSite) {
      setSelectedSiteInfo(
        selectedSite.id,
        selectedSite.displayName || selectedSite.name,
      );
    }
  }, [selectedSite, setSelectedSiteInfo]);

  return (
    <div
      data-testid="site-picker"
      className={cn(
        layout === "stacked" ? "flex w-full flex-col gap-2" : "flex items-center gap-3",
        headerClass,
      )}
    >
      {showSelect && (
        <>
          <label
            className={cn(
              "text-xs font-medium uppercase tracking-wide",
              headerTextVariant === "light"
                ? "text-white/90 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]"
                : "text-muted-foreground",
            )}
          >
            Database:
          </label>
          <div
            className={
              layout === "stacked" ? "relative w-full overflow-hidden" : "relative"
            }
          >
            <select
              value={value}
              onChange={(e) => {
                const nextId = e.target.value;
                const nextSite = sites.find((site) => site.id === nextId);
                if (nextSite) {
                  setSelectedSiteInfo(
                    nextSite.id,
                    nextSite.displayName || nextSite.name,
                  );
                }
                onChange(nextId);
              }}
              disabled={loading}
              data-testid="site-select"
              className={cn(
                "appearance-none rounded-md border pr-8 shadow-xs transition-colors focus:outline-none focus:ring-2",
                layout === "stacked"
                  ? "w-full px-2 py-1.5 text-sm truncate"
                  : "px-3 py-1.5 text-sm",
                headerTextVariant === "light"
                  ? "border-white/40 bg-white/15 text-white focus:border-white/60 focus:ring-white/30 [&_option]:bg-background [&_option]:text-foreground"
                  : "border-border bg-background text-foreground hover:border-input focus:border-primary focus:ring-primary/20",
              )}
            >
              <optgroup label="Component Sites">
                {sites
                  .filter((s) => !s.isPortal)
                  .map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.displayName}
                    </option>
                  ))}
              </optgroup>
              <optgroup label="Portal">
                {sites
                  .filter((s) => s.isPortal)
                  .map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.displayName}
                    </option>
                  ))}
              </optgroup>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
              <svg
                className={cn(
                  "h-4 w-4",
                  headerTextVariant === "light"
                    ? "text-white/80"
                    : "text-muted-foreground",
                )}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </div>
          </div>
        </>
      )}
      {selectedSite && (
        <div
          className={
            layout === "stacked"
              ? "flex flex-wrap items-center gap-2 text-xs"
              : "flex items-center gap-3 text-xs"
          }
        >
          {showVisit && (
            <a
              href={visitUrl || selectedSite.baseUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground transition-colors duration-150 hover:text-foreground"
            >
              Visit site →
            </a>
          )}
          {showAuth && displaySignedIn && (
            <>
              <span
                className={
                  headerTextVariant === "light"
                    ? "text-white/95 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]"
                    : "text-muted-foreground"
                }
              >
                Logged in as {displayName || "—"}
              </span>
              <button
                type="button"
                onClick={async () => {
                  setAuthBusy(true);
                  setAuthError(null);
                  try {
                    await logoutVeupathdb();
                    setAuthToken(null);
                    setAuthStatus({ signedIn: false });
                    setVeupathdbAuth(false, null);
                  } catch {
                    setAuthError("Failed to log out. Please try again.");
                  } finally {
                    setAuthBusy(false);
                  }
                }}
                className={
                  headerTextVariant === "light"
                    ? "text-white/95 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)] transition-colors duration-150 hover:text-primary hover:drop-shadow-none"
                    : "text-muted-foreground transition-colors duration-150 hover:text-foreground"
                }
              >
                Log out
              </button>
            </>
          )}
          {showAuth && authDisplay === "button" && !displaySignedIn && (
            <button
              type="button"
              onClick={() => setShowLoginModal(true)}
              className={
                headerTextVariant === "light"
                  ? "text-white/95 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)] transition-colors duration-150 hover:text-primary hover:drop-shadow-none"
                  : "text-muted-foreground transition-colors duration-150 hover:text-foreground"
              }
            >
              Sign in →
            </button>
          )}
        </div>
      )}
      {showAuth && authDisplay === "inline" && !displaySignedIn && (
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
    </div>
  );
}
