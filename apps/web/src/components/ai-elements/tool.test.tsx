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

  it("renders a Python-repr string verbatim instead of swallowing it", () => {
    const repr = "{'id': 'plan_31f80c5485cd', 'title': 'My plan'}";
    render(<ToolOutput output={repr} errorText={undefined} />);
    expect(screen.getByText(repr)).toBeInTheDocument();
  });

  it("shows errorText under an Error heading", () => {
    render(<ToolOutput output={undefined} errorText="Failed" />);
    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders nothing when there is neither output nor error", () => {
    const { container } = render(<ToolOutput output={null} errorText={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
