/**
 * Widget registry — maps WDK displayType to React components.
 *
 * Dispatch order:
 * 1. Composite widgets claim groups of params (e.g., PhyleticProfile)
 * 2. Unclaimed visible params route by displayType
 * 3. Hidden unclaimed params → skip rendering, collect defaults
 */

import type { ParamSpec } from "@/features/strategy/parameters/spec";

/** Resolve the canonical displayType string from a param spec. */
export function resolveDisplayType(spec: ParamSpec): string {
  return (spec.displayType || "").trim().toLowerCase();
}

/** Check if a param is hidden (should not render UI). */
export function isHiddenParam(spec: ParamSpec): boolean {
  return spec.isVisible === false || spec.group === "_hidden";
}

/** Check if a param belongs to the "advancedParams" group. */
export function isAdvancedParam(spec: ParamSpec): boolean {
  return spec.group === "advancedParams";
}

/**
 * Canonical display type constants matching WDK's enum values.
 * Unknown values fall back to STRING (plain text input).
 */
export const DISPLAY_TYPES = {
  TREE_BOX: "treebox",
  TYPE_AHEAD: "typeahead",
  SELECT: "select",
  CHECK_BOX: "checkbox",
  STRING: "",
} as const;

export type DisplayType = (typeof DISPLAY_TYPES)[keyof typeof DISPLAY_TYPES];
