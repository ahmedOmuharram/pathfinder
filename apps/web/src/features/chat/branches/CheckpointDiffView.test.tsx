/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CheckpointDiffView } from "./CheckpointDiffView";

const leftValues = { phase: "scoping", messages: ["hello"] };
const rightValues = { phase: "discovery", messages: ["hello", "world"] };

const mockClient = vi.fn();

vi.mock("@/lib/api/client", () => ({
  client: (...args: unknown[]) => mockClient(...args),
}));

vi.mock("json-diff-kit/dist/viewer.css", () => ({}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("CheckpointDiffView", () => {
  it("shows loading text while queries are pending", () => {
    mockClient.mockImplementation(() => new Promise(() => {}));

    renderWithProviders(
      <CheckpointDiffView
        chatId="chat-1"
        leftCp="cp-left"
        rightCp="cp-right"
      />,
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders the diff viewer when both queries resolve", async () => {
    mockClient.mockImplementation(
      (cfg: { url: string }) => {
        if (cfg.url.includes("cp-left")) {
          return Promise.resolve({
            data: { values: leftValues },
            status: 200,
            statusText: "OK",
            headers: new Headers(),
          });
        }
        return Promise.resolve({
          data: { values: rightValues },
          status: 200,
          statusText: "OK",
          headers: new Headers(),
        });
      },
    );

    const { container } = renderWithProviders(
      <CheckpointDiffView
        chatId="chat-1"
        leftCp="cp-left"
        rightCp="cp-right"
      />,
    );

    await screen.findByText((_, el) => {
      if (el === null) return false;
      return el.className.includes("json-diff-viewer");
    }).catch(() => {});

    await vi.waitFor(() => {
      expect(
        container.querySelector("[class*='json-diff-viewer']"),
      ).toBeInTheDocument();
    });
  });

  it("renders an empty diff when values are missing", async () => {
    mockClient.mockResolvedValue({
      data: {},
      status: 200,
      statusText: "OK",
      headers: new Headers(),
    });

    const { container } = renderWithProviders(
      <CheckpointDiffView
        chatId="chat-1"
        leftCp="cp-left"
        rightCp="cp-right"
      />,
    );

    await vi.waitFor(() => {
      expect(
        container.querySelector("[class*='json-diff-viewer']"),
      ).toBeInTheDocument();
    });
  });
});
