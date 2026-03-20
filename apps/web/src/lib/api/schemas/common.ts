/**
 * Shared Zod schema helpers for API response validation.
 *
 * Convention: schemas in this layer are *permissive* — they use `.passthrough()`
 * on objects so the backend can add new fields without breaking the frontend.
 */
import { z } from "zod";

/** ISO-8601 datetime string. Intentionally loose (plain `z.string()`) because
 *  the backend sometimes returns non-standard suffixes. */
export const DateTimeString = z.string();

/** UUID v4 string. */
export const UuidString = z
  .string()
  .regex(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    "Expected UUID",
  );

/** Flexible record for open-ended parameter maps. */
export const ParamRecord = z.record(z.string(), z.unknown());
