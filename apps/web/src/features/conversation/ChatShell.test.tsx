/**
 * @vitest-environment jsdom
 */
import type * as ReactQueryModule from "@tanstack/react-query";
import { describe, it, expect, beforeEach, vi } from "vitest";

import { computeChatResolution, isStrategyRoute } from "./ChatShell";

type ReactQueryExports = typeof ReactQueryModule;

describe("ChatShell.computeChatResolution", () => {
  it("uses generated id and allowMissing=true on bare /conversation", () => {
    const r = computeChatResolution({
      pathname: "/conversation",
      generatedChatId: "gen-1",
    });
    expect(r.conversationId).toBe("gen-1");
    expect(r.allowMissing).toBe(true);
  });

  it("keeps allowMissing=true after URL rewrites to /conversation/<generated-id>", () => {
    const r = computeChatResolution({
      pathname: "/conversation/gen-1",
      generatedChatId: "gen-1",
    });
    expect(r.conversationId).toBe("gen-1");
    expect(r.allowMissing).toBe(true);
  });

  it("uses URL id and allowMissing=false when navigating to an existing conversation", () => {
    const r = computeChatResolution({
      pathname: "/conversation/existing-id",
      generatedChatId: "gen-1",
    });
    expect(r.conversationId).toBe("existing-id");
    expect(r.allowMissing).toBe(false);
  });

  it("allows missing when the URL id happens to equal a client-generated id", () => {
    const r = computeChatResolution({
      pathname: "/conversation/gen-1",
      generatedChatId: "gen-1",
    });
    expect(r.allowMissing).toBe(true);
  });
});

describe("ChatShell.isStrategyRoute", () => {
  it("returns false for the bare conversation route", () => {
    expect(isStrategyRoute("/plasmodb/conversation/conv-1")).toBe(false);
    expect(isStrategyRoute("/plasmodb/conversation")).toBe(false);
  });

  it("returns true for the strategy page route", () => {
    expect(isStrategyRoute("/plasmodb/conversation/conv-1/strategy")).toBe(true);
  });

  it("returns true for the strategy step deep-link route", () => {
    expect(isStrategyRoute("/plasmodb/conversation/conv-1/strategy/step/step_1")).toBe(
      true,
    );
  });
});

describe("ChatShell integration: no redirect during first-send URL rewrite", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("ChatView does not invoke redirect() when conversationId matches the generated id but detail 404s", async () => {
    const redirectSpy = vi.fn();
    vi.doMock("next/navigation", () => ({
      redirect: redirectSpy,
      usePathname: () => "/conversation/gen-xyz",
      useParams: () => ({ conversationId: "/conversation/gen-xyz".split("/").pop() }),
    }));
    vi.doMock("@tanstack/react-query", async () => {
      const actual = await vi.importActual<ReactQueryExports>("@tanstack/react-query");
      return {
        ...actual,
        useQuery: (opts: { queryKey: readonly unknown[] }) => {
          const key = opts.queryKey.join("/");
          if (key.includes("/detail")) {
            return { data: null, isFetched: true, isPending: false };
          }
          return { data: [], isFetched: true, isPending: false };
        },
      };
    });
    vi.doMock("./ChatThread", () => ({
      ChatThread: () => null,
    }));
    vi.doMock("./branches/BranchSwitcher", () => ({
      BranchSwitcher: () => null,
    }));
    vi.doMock("nuqs", () => ({
      useQueryState: () => [null, () => {}],
      parseAsString: {},
    }));

    const { ChatView } = await import("./ChatView");
    const { render } = await import("@testing-library/react");

    render(<ChatView conversationId="gen-xyz" allowMissing={true} />);

    expect(redirectSpy).not.toHaveBeenCalled();
  });

  it("ChatView passes the strategy and siteId into the rail StrategyPanel when steps exist", async () => {
    const strategyPanelSpy = vi.fn();
    vi.doMock("next/navigation", () => ({
      redirect: vi.fn(),
      usePathname: () => "/conversation/with-steps",
      useParams: () => ({
        conversationId: "/conversation/with-steps".split("/").pop(),
      }),
    }));
    vi.doMock("@tanstack/react-query", async () => {
      const actual = await vi.importActual<ReactQueryExports>("@tanstack/react-query");
      return {
        ...actual,
        useQuery: (opts: { queryKey: readonly unknown[] }) => {
          const key = opts.queryKey.join("/");
          if (key.includes("/detail")) {
            return {
              data: {
                id: "with-steps",
                name: "strat",
                siteId: "plasmodb",
                steps: [{ id: "s1" }],
                rootStepId: "s1",
                recordType: "gene",
                isSaved: false,
                createdAt: "2026-04-17T00:00:00Z",
                updatedAt: "2026-04-17T00:00:00Z",
              },
              isFetched: true,
              isPending: false,
            };
          }
          return { data: [], isFetched: true, isPending: false };
        },
      };
    });
    vi.doMock("./ChatThread", () => ({ ChatThread: () => null }));
    vi.doMock("./branches/BranchSwitcher", () => ({ BranchSwitcher: () => null }));
    vi.doMock("nuqs", () => ({
      useQueryState: () => [null, () => {}],
      parseAsString: {},
    }));
    vi.doMock("./rail/StrategyPanel", () => ({
      StrategyPanel: (props: { strategy: { id: string } | null; siteId: string }) => {
        strategyPanelSpy(props);
        return <div data-testid="strategy-panel" />;
      },
    }));

    const { ChatView } = await import("./ChatView");
    const { render } = await import("@testing-library/react");
    const { useRightRailStore } = await import("@/state/useRightRailStore");

    // Force the rail to be open on the strategy panel for this test.
    useRightRailStore.setState({ openPanel: "strategy" });

    render(<ChatView conversationId="with-steps" allowMissing={false} />);

    expect(strategyPanelSpy).toHaveBeenCalled();
    const lastCall = strategyPanelSpy.mock.calls.at(-1);
    if (lastCall === undefined) throw new Error("no call");
    const props = lastCall[0] as { strategy: { id: string } | null; siteId: string };
    expect(props.strategy?.id).toBe("with-steps");
    expect(props.siteId).toBe("plasmodb");
  });

  it("ChatView passes a strategy with no steps into the rail StrategyPanel (rail handles empty state)", async () => {
    const strategyPanelSpy = vi.fn();
    vi.doMock("next/navigation", () => ({
      redirect: vi.fn(),
      usePathname: () => "/conversation/no-steps",
      useParams: () => ({ conversationId: "/conversation/no-steps".split("/").pop() }),
    }));
    vi.doMock("@tanstack/react-query", async () => {
      const actual = await vi.importActual<ReactQueryExports>("@tanstack/react-query");
      return {
        ...actual,
        useQuery: (opts: { queryKey: readonly unknown[] }) => {
          const key = opts.queryKey.join("/");
          if (key.includes("/detail")) {
            return {
              data: {
                id: "no-steps",
                name: "strat",
                siteId: "plasmodb",
                steps: [],
                rootStepId: null,
                recordType: null,
                isSaved: false,
                createdAt: "2026-04-17T00:00:00Z",
                updatedAt: "2026-04-17T00:00:00Z",
              },
              isFetched: true,
              isPending: false,
            };
          }
          return { data: [], isFetched: true, isPending: false };
        },
      };
    });
    vi.doMock("./ChatThread", () => ({ ChatThread: () => null }));
    vi.doMock("./branches/BranchSwitcher", () => ({ BranchSwitcher: () => null }));
    vi.doMock("nuqs", () => ({
      useQueryState: () => [null, () => {}],
      parseAsString: {},
    }));
    vi.doMock("./rail/StrategyPanel", () => ({
      StrategyPanel: (props: {
        strategy: { steps: unknown[] } | null;
        siteId: string;
      }) => {
        strategyPanelSpy(props);
        return <div data-testid="strategy-panel" />;
      },
    }));

    const { ChatView } = await import("./ChatView");
    const { render } = await import("@testing-library/react");
    const { useRightRailStore } = await import("@/state/useRightRailStore");

    useRightRailStore.setState({ openPanel: "strategy" });

    render(<ChatView conversationId="no-steps" allowMissing={false} />);

    expect(strategyPanelSpy).toHaveBeenCalled();
    const lastCall = strategyPanelSpy.mock.calls.at(-1);
    if (lastCall === undefined) throw new Error("no call");
    const props = lastCall[0] as {
      strategy: { steps: unknown[] } | null;
      siteId: string;
    };
    expect(props.strategy?.steps).toEqual([]);
  });

  it("ChatView does invoke redirect() when conversationId is an unknown id (not client-generated)", async () => {
    const redirectSpy = vi.fn();
    vi.doMock("next/navigation", () => ({
      redirect: redirectSpy,
      usePathname: () => "/conversation/stranger",
      useParams: () => ({ conversationId: "/conversation/stranger".split("/").pop() }),
    }));
    vi.doMock("@tanstack/react-query", async () => {
      const actual = await vi.importActual<ReactQueryExports>("@tanstack/react-query");
      return {
        ...actual,
        useQuery: (opts: { queryKey: readonly unknown[] }) => {
          const key = opts.queryKey.join("/");
          if (key.includes("/detail")) {
            return { data: null, isFetched: true, isPending: false };
          }
          return { data: [], isFetched: true, isPending: false };
        },
      };
    });
    vi.doMock("./ChatThread", () => ({
      ChatThread: () => null,
    }));
    vi.doMock("./branches/BranchSwitcher", () => ({
      BranchSwitcher: () => null,
    }));
    vi.doMock("nuqs", () => ({
      useQueryState: () => [null, () => {}],
      parseAsString: {},
    }));

    const { ChatView } = await import("./ChatView");
    const { render } = await import("@testing-library/react");

    render(<ChatView conversationId="stranger" allowMissing={false} />);

    // useParams mock omits siteId, so the redirect interpolates an empty
    // segment. The production code prefixes the route with `/${siteId}/`.
    expect(redirectSpy).toHaveBeenCalledWith("//conversation");
  });
});
