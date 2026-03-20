import type { z } from "zod";

class SchemaValidationError extends Error {
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
    // Cookie auth is the public API contract; include it for browser + SSR.
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
    let msg = `HTTP ${resp.status} ${resp.statusText}`;
    if (typeof data === "object" && data !== null && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail)) {
        // FastAPI validation errors: [{loc, msg, type}, ...]
        msg = detail
          .map((e: unknown) =>
            typeof e === "object" && e != null && "msg" in e
              ? String((e as { msg: unknown }).msg)
              : String(e),
          )
          .join("; ");
      } else {
        msg = String(detail);
      }
    }
    throw new APIError(msg, {
      status: resp.status,
      statusText: resp.statusText,
      url,
      data,
    });
  }

  return data as T;
}

/**
 * Like `requestJson`, but validates the response against a Zod schema.
 *
 * Usage:
 *   const strategy = await requestJsonValidated(StrategySchema, `/api/v1/strategies/${id}`);
 *
 * On validation failure a `SchemaValidationError` is thrown with the Zod issues
 * attached.  In development mode the issues are also logged to console.warn so
 * you notice contract drift without crashing the UI during early adoption.
 */
export async function requestJsonValidated<T>(
  schema: z.ZodType<T>,
  path: string,
  args?: {
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    query?: Record<string, string | number | boolean | null | undefined>;
    body?: unknown;
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
): Promise<T> {
  const raw = await requestJson<unknown>(path, args);
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
