export type RequestConfig<D = unknown> = {
  method: "get" | "post" | "put" | "patch" | "delete";
  url: string;
  params?: Record<string, string | number | boolean | undefined>;
  data?: D;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

export type ResponseConfig<T = unknown> = {
  data: T;
  status: number;
  statusText: string;
  headers: Headers;
};

export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly data: unknown;
  constructor(init: { status: number; statusText: string; data: unknown }) {
    super(`${init.status} ${init.statusText}`);
    this.status = init.status;
    this.statusText = init.statusText;
    this.data = init.data;
  }
}

export async function client<TData>(cfg: RequestConfig): Promise<ResponseConfig<TData>> {
  const url = new URL(cfg.url, window.location.origin);
  if (cfg.params) {
    for (const [k, v] of Object.entries(cfg.params)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  const init: RequestInit = {
    method: cfg.method.toUpperCase(),
    headers: {
      "content-type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      ...cfg.headers,
    },
    credentials: "include",
  };
  if (cfg.data !== undefined) {
    init.body = JSON.stringify(cfg.data);
  }
  if (cfg.signal !== undefined) {
    init.signal = cfg.signal;
  }
  const resp = await fetch(url.toString(), init);
  const contentType = resp.headers.get("content-type") ?? "";
  // Match both ``application/json`` and ``application/problem+json`` so the
  // FastAPI ProblemDetail body lands on ``data`` as a parsed object.
  const data: unknown = contentType.includes("json")
    ? await (resp.json() as Promise<unknown>)
    : await resp.text();
  if (!resp.ok) {
    throw new ApiError({ status: resp.status, statusText: resp.statusText, data });
  }
  return {
    data: data as TData,
    status: resp.status,
    statusText: resp.statusText,
    headers: resp.headers,
  };
}

export default client;
