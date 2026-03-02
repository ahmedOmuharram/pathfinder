import { AppError } from "@/lib/errors/AppError";
import { requestJson } from "./http";

// VEuPathDB auth bridge -- always authenticates against the portal

const AUTH_SITE_ID = "veupathdb";

export async function getVeupathdbAuthStatus(): Promise<{
  signedIn: boolean;
  name: string | null;
  email: string | null;
}> {
  return await requestJson(`/api/v1/veupathdb/auth/status`, {
    query: { siteId: AUTH_SITE_ID },
  });
}

export async function loginVeupathdb(
  email: string,
  password: string,
): Promise<{ success: boolean; authToken?: string }> {
  if (!email || !password) {
    throw new AppError("Email and password are required.", "INVARIANT_VIOLATION");
  }
  return await requestJson(`/api/v1/veupathdb/auth/login`, {
    method: "POST",
    query: { siteId: AUTH_SITE_ID },
    body: { email, password },
  });
}

export async function logoutVeupathdb(): Promise<{ success: boolean }> {
  return await requestJson(`/api/v1/veupathdb/auth/logout`, { method: "POST" });
}

/**
 * Re-derive the internal ``pathfinder-auth`` token from a live VEuPathDB session.
 * Called on page load when the internal token is missing/expired.
 */
export async function refreshAuth(): Promise<{ success: boolean; authToken?: string }> {
  return await requestJson(`/api/v1/veupathdb/auth/refresh`, { method: "POST" });
}
