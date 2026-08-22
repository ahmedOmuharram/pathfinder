/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  useExternalStoreRuntime,
} from "@assistant-ui/react";
import type { ThreadMessageLike } from "@assistant-ui/react";
import type { DataPartKind } from "@pathfinder/shared";

import { AssistantMessage, UserMessage } from "./MessageRenderer";
import { coreDataPartComponents } from "./coreDataParts";
import { strategyDataPartComponents } from "./strategyDataParts";
import { dataPartComponents } from "./contentComponents";

const toastError = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: { error: toastError, success: vi.fn(), message: vi.fn() },
  Toaster: () => null,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/plasmodb/conversation/conv-1",
}));

// A kind this app never registers, in the shape a second assistant would use.
const FOREIGN_KIND = "data-other.gene-view";

function Thread({ content }: { content: ThreadMessageLike["content"] }) {
  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages: [{ role: "assistant", content }],
    convertMessage: (message) => message,
    onNew: async () => undefined,
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Messages components={{ AssistantMessage, UserMessage }} />
    </AssistantRuntimeProvider>
  );
}

describe("dataPartComponents merge", () => {
  it("contains every core renderer", () => {
    for (const kind of Object.keys(coreDataPartComponents)) {
      expect(Object.hasOwn(dataPartComponents, kind)).toBe(true);
    }
  });

  it("contains every strategy renderer", () => {
    for (const kind of Object.keys(strategyDataPartComponents)) {
      expect(Object.hasOwn(dataPartComponents, kind)).toBe(true);
    }
  });

  it("keeps the two halves disjoint", () => {
    const core = new Set(Object.keys(coreDataPartComponents));
    const overlap = Object.keys(strategyDataPartComponents).filter((kind) =>
      core.has(kind),
    );
    expect(overlap).toEqual([]);
  });

  it("adds nothing beyond the two halves", () => {
    const halves = new Set([
      ...Object.keys(coreDataPartComponents),
      ...Object.keys(strategyDataPartComponents),
    ]);
    expect(new Set(Object.keys(dataPartComponents))).toEqual(halves);
  });

  it("has no renderer for a kind another assistant registers", () => {
    const kind: DataPartKind = FOREIGN_KIND;
    expect(Object.hasOwn(dataPartComponents, kind)).toBe(false);
  });
});

describe("message dispatch", () => {
  it("renders a core part through the merged map", () => {
    render(
      <Thread
        content={[
          {
            type: "data-task-completed",
            data: { taskId: "t1", status: "success" },
          },
        ]}
      />,
    );
    expect(screen.getByTestId("data-task-completed")).toBeInTheDocument();
    expect(toastError).not.toHaveBeenCalled();
  });

  it("renders a strategy part through the merged map", () => {
    render(
      <Thread
        content={[
          {
            type: "data-strategy-link",
            data: { strategyId: "s1", url: "https://plasmodb.org/s1", title: "Test" },
          },
        ]}
      />,
    );
    expect(screen.getByTestId("data-strategy-link")).toBeInTheDocument();
    expect(toastError).not.toHaveBeenCalled();
  });

  it("falls back and reports when the kind has no renderer", () => {
    render(<Thread content={[{ type: FOREIGN_KIND, data: { count: 1 } }]} />);
    expect(toastError).toHaveBeenCalledWith(
      `Unknown data part: ${FOREIGN_KIND}`,
      expect.anything(),
    );
  });
});
