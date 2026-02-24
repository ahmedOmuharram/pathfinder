"use client";

import { useEffect, useState } from "react";
import {
  getVeupathdbAuthStatus,
  listSites,
  loginVeupathdb,
  setVeupathdbToken,
  logoutVeupathdb,
} from "@/lib/api/client";
import type { VEuPathDBSite as Site } from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { Modal } from "@/lib/components/Modal";

interface SitePickerProps {
  value: string;
  onChange: (siteId: string) => void;
  showSelect?: boolean;
  showAuth?: boolean;
  showVisit?: boolean;
  layout?: "inline" | "stacked";
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

export function SitePicker({
  value,
  onChange,
  showSelect = true,
  showAuth = true,
  showVisit = true,
  layout = "inline",
}: SitePickerProps) {
  const [sites, setSites] = useState<Site[]>(FALLBACK_SITES);
  const [loading, setLoading] = useState(true);
  const [authStatus, setAuthStatus] = useState<{
    signedIn: boolean;
    name?: string | null;
  } | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [authMode, setAuthMode] = useState<"password" | "token">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);
  const setVeupathdbAuth = useSessionStore((state) => state.setVeupathdbAuth);
  const setAuthToken = useSessionStore((state) => state.setAuthToken);
  const setSelectedSiteInfo = useSessionStore((state) => state.setSelectedSiteInfo);

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
    getVeupathdbAuthStatus(value)
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
      className={
        layout === "stacked" ? "flex w-full flex-col gap-2" : "flex items-center gap-3"
      }
    >
      {showSelect && (
        <>
          <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
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
              className={`appearance-none rounded-md border border-border bg-card pr-8 text-foreground transition-colors hover:border-input focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                layout === "stacked"
                  ? "w-full px-2 py-1.5 text-sm truncate"
                  : "px-3 py-2 text-sm"
              }`}
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
                className="h-4 w-4 text-muted-foreground"
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
          {showAuth && authStatus?.signedIn && (
            <>
              <span className="text-muted-foreground">
                Logged in as {authStatus?.name ? `${authStatus.name}` : ""}
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
                className="text-muted-foreground transition-colors duration-150 hover:text-foreground"
              >
                Log out
              </button>
            </>
          )}
          {showAuth && !authStatus?.signedIn && (
            <button
              type="button"
              onClick={() => setShowLoginModal(true)}
              className="text-muted-foreground transition-colors duration-150 hover:text-foreground"
            >
              Sign in →
            </button>
          )}
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
          <div className="text-base font-semibold text-foreground">
            Sign in required
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Please sign in to VEuPathDB to continue.
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            We do not store your login information.
          </p>
          <div className="mt-4 flex items-center gap-2 text-xs">
            <button
              type="button"
              onClick={() => setAuthMode("password")}
              className={`rounded-md px-3 py-1.5 transition-colors duration-150 ${
                authMode === "password"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              Using username and password
            </button>
            <button
              type="button"
              onClick={() => setAuthMode("token")}
              className={`rounded-md px-3 py-1.5 transition-colors duration-150 ${
                authMode === "token"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              (Advanced) Using authentication token
            </button>
          </div>
          {authMode === "password" && (
            <div className="mt-4 space-y-3">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                className="w-full rounded-md border border-border px-3 py-2 text-sm"
              />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full rounded-md border border-border px-3 py-2 text-sm"
              />
            </div>
          )}
          {authMode === "token" && (
            <div className="mt-4">
              <textarea
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste VEuPathDB Authorization token"
                className="h-24 w-full rounded-md border border-border px-3 py-2 text-sm"
              />
              <p className="mt-2 text-xs text-muted-foreground">
                If you prefer not to login from the UI, you can provide the
                authentication token instead.
              </p>
            </div>
          )}
          {authError && (
            <div className="mt-3 text-xs text-destructive">{authError}</div>
          )}
          <div className="mt-4 flex items-center justify-end gap-2">
            <button
              type="button"
              disabled={authBusy}
              onClick={async () => {
                setAuthError(null);
                setAuthBusy(true);
                try {
                  let result: { success: boolean; authToken?: string };
                  if (authMode === "password") {
                    result = await loginVeupathdb(value, email, password);
                  } else {
                    result = await setVeupathdbToken(token);
                  }
                  if (result.authToken) {
                    setAuthToken(result.authToken);
                  }
                  const status = await getVeupathdbAuthStatus(value);
                  setAuthStatus(status);
                  setVeupathdbAuth(status.signedIn, status.name ?? null);
                  if (status.signedIn) {
                    setShowLoginModal(false);
                  } else {
                    setAuthError("Login failed. Please try again.");
                  }
                } catch {
                  setAuthError("Login failed. Please try again.");
                } finally {
                  setAuthBusy(false);
                }
              }}
              className="rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground transition-colors duration-150 disabled:opacity-60"
            >
              {authBusy ? "Signing in..." : "Sign in"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
