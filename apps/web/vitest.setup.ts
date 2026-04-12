import { createElement, type ComponentType, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { afterEach, vi } from "vitest";
import { createTestQueryClient } from "./src/lib/query/testing";

type WrapperComponent = ComponentType<{ children: ReactNode }>;

function withQueryClient(Wrapper?: WrapperComponent): WrapperComponent {
  const queryClient = createTestQueryClient();

  function QueryClientWrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      Wrapper ? createElement(Wrapper, { children }) : children,
    );
  }

  return QueryClientWrapper;
}

vi.mock("@testing-library/react", async () => {
  const actual = await vi.importActual<typeof import("@testing-library/react")>(
    "@testing-library/react",
  );

  return {
    ...actual,
    render: (
      ui: Parameters<typeof actual.render>[0],
      options?: Parameters<typeof actual.render>[1],
    ) =>
      actual.render(ui, {
        ...(options ?? {}),
        wrapper: withQueryClient(options?.wrapper as WrapperComponent | undefined),
      }),
    renderHook: <Result, Props>(
      render: (initialProps: Props) => Result,
      options?: Parameters<typeof actual.renderHook<Result, Props>>[1],
    ) =>
      actual.renderHook(render, {
        ...(options ?? {}),
        wrapper: withQueryClient(options?.wrapper as WrapperComponent | undefined),
      }),
  };
});

afterEach(async () => {
  const { cleanup } = await import("@testing-library/react");
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});
