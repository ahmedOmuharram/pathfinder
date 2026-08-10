/**
 * The one encoding for a range inside the parameter form.
 *
 * A range lives in the form as a single string because the form holds one
 * value per parameter, so min and max have to share it. There were three
 * implementations of that packing: `paramValue.ts` and `NumberRangeParam`
 * split on the first "-" after position 0, and `DateRangeParam` split on ":".
 *
 * The "-" variant cannot work for dates: "2026-01-01-2026-12-31" splits into
 * min "2026" and max "01-01-2026-12-31". And because the date widget wrote
 * ":" while the codec read "-", a stored date range did not survive being
 * opened in the editor at all.
 *
 * ":" is unambiguous for both: it appears in neither an ISO date nor a
 * number. This string never leaves the form - `rawToParamValue` turns it back
 * into a typed value before anything is sent to WDK.
 */

const SEPARATOR = ":";

export interface RangeParts {
  min: string;
  max: string;
}

export function encodeRange(min: string, max: string): string {
  if (min === "" && max === "") return "";
  return `${min}${SEPARATOR}${max}`;
}

export function decodeRange(value: string): RangeParts {
  const index = value.indexOf(SEPARATOR);
  if (index < 0) return { min: value, max: "" };
  return { min: value.slice(0, index), max: value.slice(index + 1) };
}
