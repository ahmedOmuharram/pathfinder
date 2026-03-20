/**
 * Extract the vocabulary from a parameter spec.
 *
 * Accepts both the generated `ParamSpec` from `@pathfinder/shared` and the
 * loose local `ParamSpec` (which carries an index signature).  Extra fields
 * (`values`, `items`, etc.) are checked with `in` so the function is safe
 * against strict types that don't declare those keys.
 */
export function extractSpecVocabulary(spec: Record<string, unknown>): unknown {
  return (
    spec["vocabulary"] ??
    spec["values"] ??
    spec["items"] ??
    spec["terms"] ??
    spec["options"] ??
    spec["allowedValues"] ??
    undefined
  );
}
