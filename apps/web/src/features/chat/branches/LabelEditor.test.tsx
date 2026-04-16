/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { toast } from "sonner";
import { LabelEditor } from "./LabelEditor";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const mockClient = vi.fn();

vi.mock("@/lib/api/client", () => ({
  client: (...args: unknown[]) => mockClient(...args),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("LabelEditor", () => {
  it("renders with existing label", () => {
    renderWithProviders(
      <LabelEditor chatId="c1" checkpointId="cp1" currentLabel="My label" />,
    );
    const input = screen.getByDisplayValue("My label");
    expect(input).toBeInTheDocument();
  });

  it("renders empty when no label", () => {
    renderWithProviders(
      <LabelEditor chatId="c1" checkpointId="cp1" currentLabel={null} />,
    );
    const input = screen.getByPlaceholderText(/label/i);
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("calls set label mutation on save", async () => {
    const user = userEvent.setup();
    mockClient.mockResolvedValueOnce({ data: {}, status: 200, statusText: "OK", headers: new Headers() });

    renderWithProviders(
      <LabelEditor chatId="c1" checkpointId="cp1" currentLabel={null} />,
    );

    const input = screen.getByPlaceholderText(/label/i);
    await user.type(input, "New label");
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mockClient).toHaveBeenCalledWith({
        method: "put",
        url: "/api/v1/chats/c1/labels/cp1",
        data: { label: "New label" },
      });
    });
    expect(toast.success).toHaveBeenCalledWith("Label saved");
  });

  it("calls delete label when input is cleared and saved", async () => {
    const user = userEvent.setup();
    mockClient.mockResolvedValueOnce({ data: {}, status: 200, statusText: "OK", headers: new Headers() });

    renderWithProviders(
      <LabelEditor chatId="c1" checkpointId="cp1" currentLabel="Old label" />,
    );

    const input = screen.getByDisplayValue("Old label");
    await user.clear(input);
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mockClient).toHaveBeenCalledWith({
        method: "delete",
        url: "/api/v1/chats/c1/labels/cp1",
      });
    });
    expect(toast.success).toHaveBeenCalledWith("Label removed");
  });

  it("shows error toast on mutation failure", async () => {
    const user = userEvent.setup();
    mockClient.mockRejectedValueOnce(new Error("Failed"));

    renderWithProviders(
      <LabelEditor chatId="c1" checkpointId="cp1" currentLabel={null} />,
    );

    const input = screen.getByPlaceholderText(/label/i);
    await user.type(input, "Broken");
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Failed");
    });
  });
});
