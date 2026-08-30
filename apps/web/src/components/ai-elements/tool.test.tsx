/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { ToolOutput } from "./tool";

describe("ToolOutput", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a non-JSON string as readable text", () => {
    render(<ToolOutput output="discovery complete: 42 genes" errorText={undefined} />);
    expect(screen.getByText("discovery complete: 42 genes")).toBeInTheDocument();
    expect(screen.getByText("Result")).toBeInTheDocument();
  });

  it("routes JSON-shaped output to a code block, not the plain-text fallback", () => {
    // A large result clipped server-side is JSON-shaped but unparseable; it
    // should still be colorized as JSON, not dumped into the readable <pre>.
    const clipped = '{"name": "inspect_search", "allowed_values": [{"value": "a"';
    const { container } = render(<ToolOutput output={clipped} errorText={undefined} />);
    expect(container.querySelector("pre.font-sans")).toBe(null);
  });

  it("shows errorText under an Error heading", () => {
    render(<ToolOutput output={undefined} errorText="Failed" />);
    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders nothing when there is neither output nor error", () => {
    const { container } = render(<ToolOutput output={null} errorText={undefined} />);
    expect(container.innerHTML).toBe("");
  });
});
