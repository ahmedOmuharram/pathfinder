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

interface SitePickerProps {
  value: string;
  onChange: (siteId: string) => void;
  showSelect?: boolean;
  showAuth?: boolean;
  showVisit?: boolean;
  layout?: "inline" | "stacked";
}

const FALLBACK_SITES: Site[] = [
  { id: "plasmodb", name: "PlasmoDB", displayName: "PlasmoDB", baseUrl: "https://plasmodb.org", projectId: "PlasmoDB", isPortal: false },
  { id: "toxodb", name: "ToxoDB", displayName: "ToxoDB", baseUrl: "https://toxodb.org", projectId: "ToxoDB", isPortal: false },
  { id: "cryptodb", name: "CryptoDB", displayName: "CryptoDB", baseUrl: "https://cryptodb.org", projectId: "CryptoDB", isPortal: false },
  { id: "veupathdb", name: "VEuPathDB", displayName: "VEuPathDB Portal", baseUrl: "https://veupathdb.org", projectId: "EuPathDB", isPortal: true },
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
  const setSelectedSiteInfo = useSessionStore((state) => state.setSelectedSiteInfo);

  useEffect(() => {
    listSites()
      .then(setSites)
      .catch(() => setSites(FALLBACK_SITES))
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
      .catch(() => {
        setAuthStatus({ signedIn: false });
        setVeupathdbAuth(false, null);
      })
      .finally(() => undefined);
  }, [value]);

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
      setSelectedSiteInfo(selectedSite.id, selectedSite.displayName || selectedSite.name);
    }
  }, [selectedSite, setSelectedSiteInfo]);

  return (
    <div
      className={
        layout === "stacked"
          ? "flex w-full flex-col gap-2"
          : "flex items-center gap-3"
      }
    >
      {showSelect && (
        <>
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Database:
          </label>
          <div
            className={
              layout === "stacked"
                ? "relative w-full overflow-hidden"
                : "relative"
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
                    nextSite.displayName || nextSite.name
                  );
                }
                onChange(nextId);
              }}
              disabled={loading}
              className={`appearance-none rounded-md border border-slate-200 bg-white pr-8 text-slate-800 transition-colors hover:border-slate-300 focus:border-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-200 ${
                layout === "stacked"
                  ? "w-full px-2 py-1.5 text-[12px] truncate"
                  : "px-3 py-2 text-[13px]"
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
                className="h-4 w-4 text-slate-400"
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
              ? "flex flex-wrap items-center gap-2 text-[11px]"
              : "flex items-center gap-3 text-[11px]"
          }
        >
          {showVisit && (
            <a
              href={visitUrl || selectedSite.baseUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-500 transition-colors hover:text-slate-700"
            >
              Visit site →
            </a>
          )}
          {showAuth && authStatus?.signedIn && (
            <>
              <span className="text-slate-600">
                Logged in as {authStatus?.name ? `${authStatus.name}` : ""}
              </span>
              <button
                type="button"
                onClick={async () => {
                  setAuthBusy(true);
                  setAuthError(null);
                  try {
                    await logoutVeupathdb();
                    setAuthStatus({ signedIn: false });
                    setVeupathdbAuth(false, null);
                  } catch {
                    setAuthError("Failed to log out. Please try again.");
                  } finally {
                    setAuthBusy(false);
                  }
                }}
                className="text-slate-500 transition-colors hover:text-slate-700"
              >
                Log out
              </button>
            </>
          )}
          {showAuth && !authStatus?.signedIn && (
            <button
              type="button"
              onClick={() => setShowLoginModal(true)}
              className="text-slate-600 transition-colors hover:text-slate-800"
            >
              Sign in →
            </button>
          )}
        </div>
      )}
      {showLoginModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
          <div className="w-full max-w-sm rounded-lg bg-white p-5 shadow-lg">
            <div className="flex items-center justify-between">
              <div className="text-base font-semibold text-slate-900">
                Sign in required
              </div>
              <button
                type="button"
                onClick={() => setShowLoginModal(false)}
                className="text-slate-400 hover:text-slate-600"
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              Please sign in to VEuPathDB to continue.
            </p>
            <p className="mt-2 text-xs text-slate-500">
              We do not store your login information.
            </p>
            <div className="mt-4 flex items-center gap-2 text-xs">
              <button
                type="button"
                onClick={() => setAuthMode("password")}
                className={`rounded-md px-3 py-1.5 ${
                  authMode === "password"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                Using username and password
              </button>
              <button
                type="button"
                onClick={() => setAuthMode("token")}
                className={`rounded-md px-3 py-1.5 ${
                  authMode === "token"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-600"
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
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Password"
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                />
              </div>
            )}
            {authMode === "token" && (
              <div className="mt-4">
                <textarea
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Paste VEuPathDB Authorization token"
                  className="h-24 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                />
                <p className="mt-2 text-xs text-slate-500">
                  If you prefer not to login from the UI, you can provide the authentication token instead.
                </p>
              </div>
            )}
            {authError && (
              <div className="mt-3 text-xs text-red-600">{authError}</div>
            )}
            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                disabled={authBusy}
                onClick={async () => {
                  setAuthError(null);
                  setAuthBusy(true);
                  try {
                    if (authMode === "password") {
                      await loginVeupathdb(value, email, password);
                    } else {
                      await setVeupathdbToken(token);
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
                className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-60"
              >
                {authBusy ? "Signing in..." : "Sign in"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

