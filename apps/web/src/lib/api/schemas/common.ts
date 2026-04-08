/**
 * Shared Zod schema helpers for API response validation.
 */
import { z } from "zod";

/** ISO-8601 datetime string. Intentionally loose (plain `z.string()`) because
 *  the backend sometimes returns non-standard suffixes. */
export const DateTimeString = z.string();

/** UUID v4 string. */
export const UuidString = z.uuid();

/** Flexible record for open-ended parameter maps. */
export const ParamRecord = z.record(z.string(), z.unknown());
