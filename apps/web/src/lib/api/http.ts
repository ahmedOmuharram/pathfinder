import { getAuthToken } from "./auth";

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export class APIError extends Error {
  status: number;
  statusText: string;
  url: string;
  data: unknown;

  constructor(
    message: string,
    args: { status: number; statusText: string; url: string; data: unknown },
  ) {
    super(message);
    this.name = "APIError";
    this.status = args.status;
    this.statusText = args.statusText;
    this.url = args.url;
    this.data = args.data;
  }
}

function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    // In the browser, use the page's own origin so every request goes through
    // the Next.js rewrite proxy (configured in next.config.js).  This keeps
    // cookies on the same origin as the page, avoiding cross-origin cookie
    // issues that cause "different session" errors when the API runs on a
    // different port (e.g. localhost:3000 → localhost:8000).
    return window.location.origin;
  }
  // Server-side (SSR / route handlers): reach the API directly.
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return base.replace(/\/+$/, "");
}

export function buildUrl(
  path: string,
  query?: Record<string, string | number | boolean | null | undefined>,
): string {
  const base = getApiBaseUrl();
  const url =
    path.startsWith("http://") || path.startsWith("https://")
      ? new URL(path)
      : new URL(path, base);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export function getAuthHeaders(
  tokenOverride?: string | null,
  opts?: { accept?: string; contentType?: string; extra?: Record<string, string> },
): Record<string, string> {
  const token = tokenOverride ?? getAuthToken();
  const headers: Record<string, string> = {
    ...(opts?.accept ? { Accept: opts.accept } : {}),
    ...(opts?.contentType ? { "Content-Type": opts.contentType } : {}),
    ...(opts?.extra ?? {}),
  };

  if (token) {
    headers.Authorization = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
  }
  return headers;
}

async function parseResponseBody(resp: Response): Promise<unknown> {
  const contentType = resp.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return await resp.json();
    } catch {
      return null;
    }
  }
  try {
    return await resp.text();
  } catch {
    return null;
  }
}

export async function requestJson<T>(
  path: string,
  args?: {
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    query?: Record<string, string | number | boolean | null | undefined>;
    body?: unknown;
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
): Promise<T> {
  const method = args?.method ?? "GET";
  const url = buildUrl(path, args?.query);

  const hasBody = args && "body" in args && args.body !== undefined;
  const headers: Record<string, string> = {
    ...getAuthHeaders(undefined, {
      accept: "application/json",
      contentType: hasBody ? "application/json" : undefined,
    }),
    ...(args?.headers ?? {}),
  };

  const resp = await fetch(url, {
    method,
    headers,
    body: hasBody ? JSON.stringify(args?.body ?? null) : undefined,
    signal: args?.signal,
    // Cookie auth is the public API contract; include it for browser + SSR.
    credentials: "include",
  });

  const data = await parseResponseBody(resp);

  if (!resp.ok) {
    const msg =
      typeof data === "object" && data && "detail" in (data as Record<string, unknown>)
        ? String((data as Record<string, unknown>).detail)
        : `HTTP ${resp.status} ${resp.statusText}`;
    throw new APIError(msg, {
      status: resp.status,
      statusText: resp.statusText,
      url,
      data,
    });
  }

  return data as T;
}
