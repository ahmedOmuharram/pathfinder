import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// Mock the http module before importing the module under test
vi.mock("@/lib/api/http", () => ({
  requestJson: vi.fn(),
  buildUrl: vi.fn((path: string) => `http://localhost:8000${path}`),
  getAuthHeaders: vi.fn((opts?: { accept?: string }) => ({
    ...(opts?.accept ? { Accept: opts.accept } : {}),
  })),
  APIError: class APIError extends Error {
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
  },
}));

import { listExperiments, seedExperiments } from "./experiments";
import { requestJson, buildUrl, getAuthHeaders } from "@/lib/api/http";
import type { ExperimentSummary } from "@pathfinder/shared";

const mockRequestJson = vi.mocked(requestJson);
const mockBuildUrl = vi.mocked(buildUrl);
const mockGetAuthHeaders = vi.mocked(getAuthHeaders);

beforeEach(() => {
  mockRequestJson.mockReset();
  mockBuildUrl.mockReset();
  mockGetAuthHeaders.mockReset();
  // Restore default implementations
  mockBuildUrl.mockImplementation((path: string) => `http://localhost:8000${path}`);
  mockGetAuthHeaders.mockImplementation((opts?: { accept?: string }) => ({
    ...(opts?.accept ? { Accept: opts.accept } : {}),
  }));
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const summaryFixture: ExperimentSummary = {
  id: "exp-1",
  name: "Test Experiment",
  siteId: "plasmodb",
  searchName: "GeneByTextSearch",
  recordType: "gene",
  mode: "single",
  status: "completed",
  f1Score: 0.85,
  sensitivity: 0.9,
  specificity: 0.8,
  totalPositives: 50,
  totalNegatives: 100,
  createdAt: "2026-01-01T00:00:00Z",
  batchId: null,
  benchmarkId: null,
  controlSetLabel: null,
  isPrimaryBenchmark: false,
};

// ---------------------------------------------------------------------------
// listExperiments
// ---------------------------------------------------------------------------

describe("listExperiments", () => {
  it("sends GET to /api/v1/experiments without query when no siteId", async () => {
    mockRequestJson.mockResolvedValue([summaryFixture]);

    const result = await listExperiments();

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments",
      {},
    );
    expect(result).toEqual([summaryFixture]);
  });

  it("includes siteId in query when provided", async () => {
    mockRequestJson.mockResolvedValue([]);

    await listExperiments("plasmodb");

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments",
      { query: { siteId: "plasmodb" } },
    );
  });

  it("passes null siteId without query (treats null like undefined)", async () => {
    mockRequestJson.mockResolvedValue([]);

    await listExperiments(null);

    expect(mockRequestJson).toHaveBeenCalledWith(
      expect.anything(),
      "/api/v1/experiments",
      {},
    );
  });

  it("returns empty array when no experiments exist", async () => {
    mockRequestJson.mockResolvedValue([]);

    const result = await listExperiments("toxodb");
    expect(result).toEqual([]);
  });

  it("returns multiple experiment summaries", async () => {
    const multiple = [
      summaryFixture,
      { ...summaryFixture, id: "exp-2", name: "Second Experiment" },
    ];
    mockRequestJson.mockResolvedValue(multiple);

    const result = await listExperiments();
    expect(result).toHaveLength(2);
  });

  it("propagates API errors", async () => {
    mockRequestJson.mockRejectedValue(new Error("Unauthorized"));

    await expect(listExperiments()).rejects.toThrow("Unauthorized");
  });
});

// ---------------------------------------------------------------------------
// seedExperiments
// ---------------------------------------------------------------------------

describe("seedExperiments", () => {
  function makeReadableStream(chunks: string[]): ReadableStream<Uint8Array> {
    const encoder = new TextEncoder();
    let index = 0;
    return new ReadableStream({
      pull(controller) {
        if (index < chunks.length) {
          controller.enqueue(encoder.encode(chunks[index]));
          index++;
        } else {
          controller.close();
        }
      },
    });
  }

  function makeFetchResponse(
    ok: boolean,
    status: number,
    body: ReadableStream<Uint8Array> | null,
  ): Response {
    return {
      ok,
      status,
      statusText: ok ? "OK" : "Internal Server Error",
      body,
      headers: new Headers(),
    } as unknown as Response;
  }

  it("parses SSE data lines and calls onMessage for each message", async () => {
    const chunks = [
      'data: {"message": "Starting seed..."}\n',
      'data: {"message": "Created strategy 1"}\n',
      'data: {"message": "Done"}\n',
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["Starting seed...", "Created strategy 1", "Done"]);
  });

  it("handles multi-chunk SSE data split across read boundaries", async () => {
    // Data line split across two chunks
    const chunks = ['data: {"messag', 'e": "Hello world"}\n'];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["Hello world"]);
  });

  it("skips non-data lines (comments, empty lines)", async () => {
    const chunks = [
      ": this is a comment\n",
      "\n",
      'data: {"message": "real message"}\n',
      "event: custom\n",
      "\n",
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["real message"]);
  });

  it("skips malformed JSON in data lines", async () => {
    const chunks = [
      "data: not valid json\n",
      'data: {"message": "good"}\n',
      "data: {broken\n",
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["good"]);
  });

  it("skips data objects without a message field", async () => {
    const chunks = [
      'data: {"status": "ok"}\n',
      'data: {"message": "has message"}\n',
      'data: {"progress": 0.5}\n',
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["has message"]);
  });

  it("throws APIError when response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(false, 500, null)),
    );

    await expect(seedExperiments(() => {})).rejects.toThrow("Seed failed: HTTP 500");
  });

  it("throws APIError when response body is null", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, null)),
    );

    // ok=true but body=null should still throw because of the !response.body check
    await expect(seedExperiments(() => {})).rejects.toThrow("Seed failed: HTTP 200");
  });

  it("calls fetch with correct method, headers, and credentials", async () => {
    const fetchSpy = vi.fn(async () =>
      makeFetchResponse(true, 200, makeReadableStream([])),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await seedExperiments(() => {});

    expect(fetchSpy).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/experiments/seed",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
  });

  it("handles an empty stream gracefully", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream([]))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual([]);
  });

  it("handles multiple data lines in a single chunk", async () => {
    const chunks = [
      'data: {"message": "one"}\ndata: {"message": "two"}\ndata: {"message": "three"}\n',
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["one", "two", "three"]);
  });
});
