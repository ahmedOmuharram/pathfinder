import { AppError } from "@/lib/errors/AppError";
import { requestJsonValidated } from "./http";
import { AuthStatusResponseSchema, AuthSuccessResponseSchema } from "./schemas/auth";

// VEuPathDB auth bridge

export async function getVeupathdbAuthStatus(siteId: string): Promise<{
  signedIn: boolean;
  name?: string | null;
  email?: string | null;
}> {
  return await requestJsonValidated(
    AuthStatusResponseSchema,
    `/api/v1/veupathdb/auth/status`,
    { query: { siteId } },
  );
}

export async function loginVeupathdb(
  email: string,
  password: string,
  siteId: string,
): Promise<{ success: boolean }> {
  if (!email || !password) {
    throw new AppError("Email and password are required.", "INVARIANT_VIOLATION");
  }
  return await requestJsonValidated(
    AuthSuccessResponseSchema,
    `/api/v1/veupathdb/auth/login`,
    {
      method: "POST",
      query: { siteId },
      body: { email, password },
    },
  );
}

export async function logoutVeupathdb(siteId: string): Promise<{ success: boolean }> {
  return await requestJsonValidated(
    AuthSuccessResponseSchema,
    `/api/v1/veupathdb/auth/logout`,
    { method: "POST", query: { siteId } },
  );
}

/**
 * Re-derive the internal ``pathfinder-auth`` token from a live VEuPathDB session.
 * Called on page load when the internal token is missing/expired.
 */
export async function refreshAuth(siteId: string): Promise<{ success: boolean }> {
  return await requestJsonValidated(
    AuthSuccessResponseSchema,
    `/api/v1/veupathdb/auth/refresh`,
    { method: "POST", query: { siteId } },
  );
}
