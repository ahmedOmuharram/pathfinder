import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import type * as HttpModule from "@/lib/api/http";

// Stub the two calls this module makes; the seed stream still builds its real
// request headers.
vi.mock("@/lib/api/http", async (importOriginal) => ({
  ...(await importOriginal<typeof HttpModule>()),
  requestJson: vi.fn(),
  buildUrl: vi.fn((path: string) => `http://localhost:8000${path}`),
}));

import { listExperiments, seedExperiments } from "./experiments";
import { requestJson, buildUrl } from "@/lib/api/http";
import type { ExperimentSummary } from "@pathfinder/shared";

const mockRequestJson = vi.mocked(requestJson);
const mockBuildUrl = vi.mocked(buildUrl);

beforeEach(() => {
  mockRequestJson.mockReset();
  mockBuildUrl.mockReset();
  mockBuildUrl.mockImplementation((path: string) => `http://localhost:8000${path}`);
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

  it("parses typed SSE frames and calls onMessage for each event's message", async () => {
    const chunks = [
      'event: seed_progress\ndata: {"type":"seed_progress","phase":"starting","message":"Starting seed..."}\n\n',
      'event: seed_strategy_complete\ndata: {"type":"seed_strategy_complete","current":1,"total":1,"name":"s","wdkStrategyId":"1","elapsed":0.2,"message":"Created strategy 1"}\n\n',
      'event: seed_complete\ndata: {"type":"seed_complete","total":1,"strategiesCreated":1,"controlSetsCreated":1,"failed":0,"message":"Done"}\n\n',
      "data: [DONE]\n\n",
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["Starting seed...", "Created strategy 1", "Done"]);
  });

  it("handles frames split across chunk boundaries", async () => {
    const chunks = [
      'event: seed_progress\ndata: {"type":"seed_progress","phase":"starting","message',
      '":"Hello world"}\n\n',
      "data: [DONE]\n\n",
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["Hello world"]);
  });

  it("skips malformed JSON frames", async () => {
    const chunks = [
      "event: seed_progress\ndata: not valid json\n\n",
      'event: seed_progress\ndata: {"type":"seed_progress","phase":"starting","message":"good"}\n\n',
      "data: [DONE]\n\n",
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["good"]);
  });

  it("throws when response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(false, 500, null)),
    );

    await expect(seedExperiments(() => {})).rejects.toThrow(/stream failed: 500/);
  });

  it("throws when response body is null", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, null)),
    );

    await expect(seedExperiments(() => {})).rejects.toThrow(/no response body/);
  });

  it("calls fetch with POST, credentials:include and the CSRF header", async () => {
    const fetchSpy = vi.fn(async () =>
      makeFetchResponse(true, 200, makeReadableStream(["data: [DONE]\n\n"])),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await seedExperiments(() => {});

    expect(fetchSpy).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/experiments/seed",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: expect.objectContaining({
          "X-Requested-With": "XMLHttpRequest",
        }),
      }),
    );
  });

  it("handles a stream with only [DONE]", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        makeFetchResponse(true, 200, makeReadableStream(["data: [DONE]\n\n"])),
      ),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual([]);
  });

  it("handles multiple events concatenated in a single chunk", async () => {
    const chunks = [
      [
        'event: seed_progress\ndata: {"type":"seed_progress","phase":"starting","message":"one"}\n\n',
        'event: seed_progress\ndata: {"type":"seed_progress","phase":"starting","message":"two"}\n\n',
        'event: seed_progress\ndata: {"type":"seed_progress","phase":"starting","message":"three"}\n\n',
        "data: [DONE]\n\n",
      ].join(""),
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeFetchResponse(true, 200, makeReadableStream(chunks))),
    );

    const messages: string[] = [];
    await seedExperiments((msg) => messages.push(msg));

    expect(messages).toEqual(["one", "two", "three"]);
  });

  it("forwards site_id as a query parameter when provided", async () => {
    const fetchSpy = vi.fn(async () =>
      makeFetchResponse(true, 200, makeReadableStream(["data: [DONE]\n\n"])),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await seedExperiments(() => {}, "plasmodb");

    expect(fetchSpy).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/experiments/seed?site_id=plasmodb",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
