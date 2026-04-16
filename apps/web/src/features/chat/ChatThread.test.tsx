/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { http } from "msw";

import { server } from "../../../vitest.msw-setup";
import { ChatThread } from "./ChatThread";

describe("ChatThread", () => {
  it("renders the thread root and composer with a textarea + send button", () => {
    server.use(
      http.post("http://localhost:3000/api/v1/chat", () => new Response(null)),
    );

    render(<ChatThread chatId="c1" />);

    expect(screen.getByPlaceholderText(/ask about strategies/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });
});
