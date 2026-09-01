/**
 * @vitest-environment jsdom
 */
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { createTestWrapper } from "@/lib/query/testing";

import { QuotaPill } from "./QuotaPill";

const QUOTA = {
  usedUsd: "1.25",
  limitUsd: "10.00",
  totalTokens: 123456,
  percent: 12.5,
  resetsAt: "2026-10-01T00:00:00Z",
};

const server = setupServer(
  http.get("http://localhost:3000/api/v1/me/quota", () => HttpResponse.json(QUOTA)),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPill() {
  const { Wrapper } = createTestWrapper();
  return render(<QuotaPill />, { wrapper: Wrapper });
}

describe("QuotaPill", () => {
  it("shows the account's spend against its monthly limit", async () => {
    renderPill();
    const pill = await screen.findByLabelText("Monthly quota");
    expect(pill).toHaveTextContent("$1.25 / $10.00");
  });

  it("is keyboard reachable and names the account-month scope in its tooltip", async () => {
    renderPill();
    const pill = await screen.findByLabelText("Monthly quota");
    expect(pill).toHaveAttribute("tabindex", "0");

    fireEvent.focus(pill);
    await waitFor(() =>
      expect(
        screen.getAllByText("Account total this month, across all conversations.")
          .length,
      ).toBeGreaterThan(0),
    );
    expect(screen.getAllByText(/123\.5K tokens · resets/).length).toBeGreaterThan(0);
  });
});
