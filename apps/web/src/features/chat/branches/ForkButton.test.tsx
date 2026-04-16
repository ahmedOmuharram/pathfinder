/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import { toast } from "sonner";
import { ForkButton } from "./ForkButton";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const mockClient = vi.fn();

vi.mock("@/lib/api/client", () => ({
  client: (...args: unknown[]) => mockClient(...args),
}));

describe("ForkButton", () => {
  it("renders a fork button", () => {
    render(
      <NuqsTestingAdapter>
        <ForkButton chatId="c1" checkpointId="cp1" />
      </NuqsTestingAdapter>,
    );
    expect(screen.getByRole("button", { name: /fork/i })).toBeInTheDocument();
  });

  it("calls fork API on click and shows success toast", async () => {
    const user = userEvent.setup();
    mockClient.mockResolvedValueOnce({
      data: { newCheckpointId: "cp-new" },
      status: 201,
      statusText: "Created",
      headers: new Headers(),
    });
    const onUrlUpdate = vi.fn();

    render(
      <NuqsTestingAdapter onUrlUpdate={onUrlUpdate} hasMemory>
        <ForkButton chatId="c1" checkpointId="cp1" />
      </NuqsTestingAdapter>,
    );

    await user.click(screen.getByRole("button", { name: /fork/i }));

    await waitFor(() => {
      expect(mockClient).toHaveBeenCalledWith({
        method: "post",
        url: "/api/v1/chats/c1/fork",
        data: { fromCheckpointId: "cp1" },
      });
    });
    expect(toast.success).toHaveBeenCalledWith("Branch created");
    expect(onUrlUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        queryString: expect.stringContaining("branch=cp-new"),
      }),
    );
  });

  it("shows error toast on API failure", async () => {
    const user = userEvent.setup();
    mockClient.mockRejectedValueOnce(new Error("Server error"));

    render(
      <NuqsTestingAdapter>
        <ForkButton chatId="c1" checkpointId="cp1" />
      </NuqsTestingAdapter>,
    );

    await user.click(screen.getByRole("button", { name: /fork/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Server error");
    });
  });
});
