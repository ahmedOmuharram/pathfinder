/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataConversationTitle } from "./DataConversationTitle";

describe("DataConversationTitle", () => {
  it("renders the title", () => {
    render(
      <DataConversationTitle data={{ title: "Malaria Gene Discovery" }} />,
    );
    expect(
      screen.getByTestId("data-conversation-title"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Title set: Malaria Gene Discovery"),
    ).toBeInTheDocument();
  });
});
