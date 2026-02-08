let authTokenGetter: (() => string | null) | null = null;

/**
 * Provide a token getter from the app layer (e.g. Zustand store).
 *
 * This keeps `lib/api/*` independent of `state/*` so it can be imported from anywhere.
 */
export function setAuthTokenGetter(getter: () => string | null) {
  authTokenGetter = getter;
}

export function getAuthToken(): string | null {
  return authTokenGetter?.() ?? null;
}
