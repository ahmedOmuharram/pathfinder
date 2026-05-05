/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import type { Strategy } from "@pathfinder/shared";
import { strategyQueryKey } from "@/lib/api/strategy";
import { listModelsQueryKey } from "@pathfinder/shared/generated/hooks/useListModels";

import { OptimizeLauncherForm } from "../OptimizeLauncherForm";

const conversationId = "00000000-0000-4000-8000-000000000001";

const fakeStrategy: Strategy = {
  id: conversationId,
  name: "Test",
  siteId: "plasmodb",
  recordType: "transcript",
  steps: [
    {
      id: "100",
      searchName: "GenesByGoTerm",
      operator: null,
      displayName: "GO term filter",
      parameters: {},
      colocationParams: null,
      estimatedSize: null,
    },
  ],
  rootStepId: "100",
  isSaved: false,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

function harness() {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  client.setQueryData(strategyQueryKey(conversationId), fakeStrategy);
  client.setQueryDefaults(listModelsQueryKey(), { staleTime: Infinity });
  client.setQueryData(listModelsQueryKey(), { models: [] });
  // Pre-seed the param-specs query so the new ParamPicker (D-4) does not
  // fire a fetch during these tests — they only care about the launcher
  // submit path.
  client.setQueryData(
    ["sites", "plasmodb", "param-specs", "transcript", "GenesByGoTerm"],
    [],
  );
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, Wrapper };
}

const originalFetch = globalThis.fetch;

beforeEach(() => {
  vi.useRealTimers();
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("OptimizeLauncherForm", () => {
  it("renders nothing when closed", () => {
    const { Wrapper } = harness();
    const { container } = render(
      <Wrapper>
        <OptimizeLauncherForm
          open={false}
          conversationId={conversationId}
          onClose={() => undefined}
        />
      </Wrapper>,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the form when open and shows the focused step as default", () => {
    const { Wrapper } = harness();
    render(
      <Wrapper>
        <OptimizeLauncherForm
          open
          conversationId={conversationId}
          onClose={() => undefined}
        />
      </Wrapper>,
    );
    expect(screen.getByTestId("optimize-launcher-form")).toBeInTheDocument();
    expect(screen.getAllByText(/GO term filter/).length).toBeGreaterThan(0);
  });

  it("rejects submit with empty params or empty criterion (toast)", async () => {
    const { Wrapper } = harness();
    const fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    render(
      <Wrapper>
        <OptimizeLauncherForm
          open
          conversationId={conversationId}
          onClose={() => undefined}
        />
      </Wrapper>,
    );
    fireEvent.click(screen.getByTestId("optimize-launcher-submit"));
    // No fetch should fire because validation fails client-side
    await waitFor(() => {
      expect(fetchSpy).not.toHaveBeenCalled();
    });
  });

  it("posts the launcher payload with chosen params + criterion", async () => {
    const { Wrapper } = harness();
    const onClose = vi.fn();
    const fetchSpy = vi.fn().mockImplementation(
      () =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              // Proper v4 UUIDs (version nibble = 4, variant = 8/9/a/b).
              taskId: "11111111-1111-4111-8111-111111111111",
              messageId: "22222222-2222-4222-8222-222222222222",
            }),
            {
              status: 200,
              headers: { "content-type": "application/json" },
            },
          ),
        ),
    );
    globalThis.fetch = fetchSpy as unknown as typeof fetch;

    render(
      <Wrapper>
        <OptimizeLauncherForm
          open
          conversationId={conversationId}
          onClose={onClose}
        />
      </Wrapper>,
    );

    const paramInput = screen.getByTestId("optimize-paramkeys-input");
    fireEvent.change(paramInput, { target: { value: "min_score, max_evalue" } });
    const criterion = screen.getByTestId("optimize-criterion-input");
    fireEvent.change(criterion, {
      target: { value: "match the gold gene set" },
    });

    fireEvent.click(screen.getByTestId("optimize-launcher-submit"));

    await waitFor(() => {
      const launcherCalls = fetchSpy.mock.calls.filter(
        (args) => String(args[0]).includes("/launchers/optimize"),
      );
      expect(launcherCalls.length).toBe(1);
    });
    const launcherCall = fetchSpy.mock.calls.find(
      (args) => String(args[0]).includes("/launchers/optimize"),
    );
    expect(launcherCall).toBeDefined();
    const [url, init] = launcherCall as [string, RequestInit];
    expect(url).toContain(
      `/api/v1/conversations/${conversationId}/launchers/optimize`,
    );
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as {
      stepId: number;
      paramKeys: string[];
      criterion: string;
      budget: number;
    };
    expect(body.stepId).toBe(100);
    expect(body.paramKeys).toEqual(["min_score", "max_evalue"]);
    expect(body.criterion).toBe("match the gold gene set");
    expect(body.budget).toBe(20);

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("surfaces a 409 launcher precondition error without crashing", async () => {
    const { Wrapper } = harness();
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "Validate requires a strategy" }),
        {
          status: 409,
          headers: { "content-type": "application/json" },
        },
      ),
    );
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    render(
      <Wrapper>
        <OptimizeLauncherForm
          open
          conversationId={conversationId}
          onClose={() => undefined}
        />
      </Wrapper>,
    );

    fireEvent.change(screen.getByTestId("optimize-paramkeys-input"), {
      target: { value: "x" },
    });
    fireEvent.change(screen.getByTestId("optimize-criterion-input"), {
      target: { value: "anything" },
    });

    fireEvent.click(screen.getByTestId("optimize-launcher-submit"));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled();
    });
    // Form remains open; no onClose call
    expect(screen.getByTestId("optimize-launcher-form")).toBeInTheDocument();
  });
});
