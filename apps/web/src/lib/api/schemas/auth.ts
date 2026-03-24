/**
 * Zod schemas for Auth API responses.
 *
 * All object schemas use .passthrough() so extra fields from the backend
 * are preserved rather than stripped.
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// Auth Status
// ---------------------------------------------------------------------------

export const AuthStatusResponseSchema = z.object({
  signedIn: z.boolean(),
  name: z.string().nullable().optional(),
  email: z.string().nullable().optional(),
});

// ---------------------------------------------------------------------------
// Login / Logout / Refresh
// ---------------------------------------------------------------------------

export const AuthSuccessResponseSchema = z.object({
  success: z.boolean(),
});
