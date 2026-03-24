import { z } from "zod";

export class SchemaValidationError extends Error {
  url: string;
  issues: unknown[];

  constructor(url: string, issues: unknown[]) {
    const summary = issues
      .slice(0, 3)
      .map((i) =>
        typeof i === "object" && i && "message" in i
          ? String((i as { message: string }).message)
          : String(i),
      )
      .join("; ");
    super(`API response validation failed for ${url}: ${summary}`);
    this.name = "SchemaValidationError";
    this.url = url;
    this.issues = issues;
  }
}

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
  const base = process.env["NEXT_PUBLIC_API_URL"] ?? "http://localhost:8000";
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

export function getAuthHeaders(opts?: {
  accept?: string;
  contentType?: string;
  extra?: Record<string, string>;
}): Record<string, string> {
  return {
    "X-Requested-With": "XMLHttpRequest",
    ...(opts?.accept != null && opts.accept !== "" ? { Accept: opts.accept } : {}),
    ...(opts?.contentType != null && opts.contentType !== ""
      ? { "Content-Type": opts.contentType }
      : {}),
    ...(opts?.extra ?? {}),
  };
}

async function parseResponseBody(resp: Response): Promise<unknown> {
  const contentType = resp.headers.get("content-type") ?? "";
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

type RequestArgs = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

function extractErrorMessage(data: unknown): string | null {
  if (typeof data !== "object" || data === null || !("detail" in data)) return null;
  const detail = (data as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e: unknown) =>
        typeof e === "object" && e != null && "msg" in e
          ? String((e as { msg: unknown }).msg)
          : String(e),
      )
      .join("; ");
  }
  return String(detail);
}

async function fetchJsonRaw(path: string, args?: RequestArgs): Promise<unknown> {
  const method = args?.method ?? "GET";
  const url = buildUrl(path, args?.query);

  const hasBody = args != null && "body" in args && args.body !== undefined;
  const headers: Record<string, string> = {
    ...getAuthHeaders({
      accept: "application/json",
      ...(hasBody ? { contentType: "application/json" } : {}),
    }),
    ...(args?.headers ?? {}),
  };

  const fetchOpts: RequestInit = {
    method,
    headers,
    credentials: "include",
  };
  if (hasBody) {
    const body = args.body;
    fetchOpts.body = JSON.stringify(body ?? null);
  }
  if (args?.signal != null) fetchOpts.signal = args.signal;
  const resp = await fetch(url, fetchOpts);

  const data = await parseResponseBody(resp);

  if (!resp.ok) {
    const msg =
      extractErrorMessage(data) ?? `HTTP ${resp.status} ${resp.statusText}`;
    throw new APIError(msg, {
      status: resp.status,
      statusText: resp.statusText,
      url,
      data,
    });
  }

  return data;
}

/**
 * Fetch JSON from the API and validate the response against a Zod schema.
 *
 * Every JSON API call goes through this function — there is no unvalidated
 * path. On validation failure a `SchemaValidationError` is thrown.
 */
export async function requestJson<T>(
  schema: z.ZodType<T>,
  path: string,
  args?: RequestArgs,
): Promise<T> {
  const raw = await fetchJsonRaw(path, args);
  const result = schema.safeParse(raw);
  if (!result.success) {
    const url = buildUrl(path, args?.query);
    const issues = result.error.issues;
    if (process.env.NODE_ENV === "development") {
      console.warn(`[SchemaValidation] ${path} response failed validation:`, issues);
    }
    throw new SchemaValidationError(url, issues);
  }
  return result.data;
}

/**
 * Fire-and-forget API call for DELETE / void endpoints.
 *
 * Throws `APIError` on non-2xx responses but does not parse or validate
 * the response body.
 */
export async function requestVoid(path: string, args?: RequestArgs): Promise<void> {
  const method = args?.method ?? "GET";
  const url = buildUrl(path, args?.query);

  const hasBody = args != null && "body" in args && args.body !== undefined;
  const headers: Record<string, string> = {
    ...getAuthHeaders({
      accept: "application/json",
      ...(hasBody ? { contentType: "application/json" } : {}),
    }),
    ...(args?.headers ?? {}),
  };

  const fetchOpts: RequestInit = {
    method,
    headers,
    credentials: "include",
  };
  if (hasBody) fetchOpts.body = JSON.stringify(args.body ?? null);
  if (args?.signal != null) fetchOpts.signal = args.signal;

  const resp = await fetch(url, fetchOpts);

  if (!resp.ok) {
    const data = await parseResponseBody(resp);
    const msg =
      extractErrorMessage(data) ?? `HTTP ${resp.status} ${resp.statusText}`;
    throw new APIError(msg, {
      status: resp.status,
      statusText: resp.statusText,
      url,
      data,
    });
  }
}

/**
 * Fetch a binary blob from the API (e.g. zip exports, HTML reports).
 * Uses the same base-URL / cookie-auth conventions as `requestJson`.
 */
export async function requestBlob(
  path: string,
  args?: {
    method?: "GET" | "POST";
    query?: Record<string, string | number | boolean | null | undefined>;
    body?: unknown;
    headers?: Record<string, string>;
  },
): Promise<Blob> {
  const method = args?.method ?? "GET";
  const url = buildUrl(path, args?.query);

  const hasBody = args != null && "body" in args && args.body !== undefined;
  const headers: Record<string, string> = {
    ...getAuthHeaders(hasBody ? { contentType: "application/json" } : {}),
    ...(args?.headers ?? {}),
  };

  const resp = await fetch(url, {
    method,
    headers,
    ...(hasBody ? { body: JSON.stringify(args.body ?? null) } : {}),
    credentials: "include",
  });

  if (!resp.ok) {
    throw new APIError(`HTTP ${resp.status} ${resp.statusText}`, {
      status: resp.status,
      statusText: resp.statusText,
      url,
      data: null,
    });
  }

  return await resp.blob();
}
