/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { StoppedNotice } from "./StoppedNotice";

describe("StoppedNotice", () => {
  it("names who stopped the response", () => {
    render(<StoppedNotice />);
    expect(screen.getByTestId("stopped-notice")).toHaveTextContent(
      "You stopped this response.",
    );
  });

  it("sets no outer margin, so the message container owns the rhythm", () => {
    render(<StoppedNotice />);
    const tokens = screen.getByTestId("stopped-notice").className.split(/\s+/);
    expect(tokens.filter((token) => /^m[ytb]-/.test(token))).toEqual([]);
  });
});
