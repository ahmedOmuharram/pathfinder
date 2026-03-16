/**
 * Extract the vocabulary from a parameter spec.
 *
 * Accepts both the generated `ParamSpec` from `@pathfinder/shared` and the
 * loose local `ParamSpec` (which carries an index signature).  Extra fields
 * (`values`, `items`, etc.) are checked with `in` so the function is safe
 * against strict types that don't declare those keys.
 */
export function extractSpecVocabulary(spec: Record<string, unknown>): unknown {
  const s = spec as Record<string, unknown>;
  return (
    s.vocabulary ??
    s.values ??
    s.items ??
    s.terms ??
    s.options ??
    s.allowedValues ??
    undefined
  );
}
