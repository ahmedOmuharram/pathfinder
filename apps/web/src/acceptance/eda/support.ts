/** Load a module that a later batch creates. Returns null while it is absent. */
export async function loadOrSkip<T>(specifier: string): Promise<T | null> {
  try {
    const loaded: unknown = await import(specifier);
    return loaded as T;
  } catch {
    return null;
  }
}
