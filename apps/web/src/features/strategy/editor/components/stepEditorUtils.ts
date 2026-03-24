/** Extract the vocabulary from a parameter spec. */
export function extractSpecVocabulary(spec: { vocabulary?: unknown }): unknown {
  return spec.vocabulary ?? undefined;
}
