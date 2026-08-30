/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { Figure } from "./Figure";

const CARD_CLASSES = ["border", "rounded-lg", "rounded-md", "shadow-card"];

function classesOf(node: HTMLElement): string[] {
  return node.className.split(/\s+/).filter((token) => token !== "");
}

describe("Figure", () => {
  it("renders its children inside the figure", () => {
    render(
      <Figure title={null} caption={null}>
        <p data-testid="body">1,543 genes</p>
      </Figure>,
    );
    const figure = screen.getByTestId("figure");
    expect(figure).toContainElement(screen.getByTestId("body"));
    expect(figure.textContent).toBe("1,543 genes");
  });

  it("titles the figure with a figcaption when a title is given", () => {
    render(
      <Figure title="log2(Fold Change)" caption={null}>
        <p>body</p>
      </Figure>,
    );
    const title = screen.getByText("log2(Fold Change)");
    expect(title.tagName).toBe("FIGCAPTION");
    expect(classesOf(title)).toEqual(["mb-2", "text-sm", "font-medium"]);
  });

  it("draws no figcaption when the title is null", () => {
    const { container } = render(
      <Figure title={null} caption="1,543 of 5,511 genes retained">
        <p>body</p>
      </Figure>,
    );
    expect(container.querySelectorAll("figcaption")).toHaveLength(0);
  });

  it("carries the numbers in a caption under the body", () => {
    render(
      <Figure title={null} caption="1,543 of 5,511 genes retained">
        <p>body</p>
      </Figure>,
    );
    const caption = screen.getByTestId("figure-caption");
    expect(caption).toHaveTextContent("1,543 of 5,511 genes retained");
    expect(classesOf(caption)).toEqual(["mt-2", "text-xs", "text-muted-foreground"]);
  });

  it("draws no caption element when the caption is null", () => {
    render(
      <Figure title="Enrichment" caption={null}>
        <p>body</p>
      </Figure>,
    );
    expect(screen.queryByTestId("figure-caption")).toBe(null);
  });

  it("separates itself with a hairline and space, never with a card", () => {
    render(
      <Figure title="Enrichment" caption="12 terms, 342 genes analyzed">
        <p>body</p>
      </Figure>,
    );
    const tokens = classesOf(screen.getByTestId("figure"));
    expect(tokens).toEqual(["my-6", "border-t", "border-border/60", "pt-4"]);
    expect(tokens.filter((token) => CARD_CLASSES.includes(token))).toEqual([]);
  });

  it("orders the title, the body and the caption", () => {
    const { container } = render(
      <Figure title="Enrichment" caption="12 terms, 342 genes analyzed">
        <p data-testid="body">body</p>
      </Figure>,
    );
    const figure = container.querySelector("figure");
    const testIds = [...(figure?.children ?? [])].map((child) =>
      child.getAttribute("data-testid"),
    );
    expect(testIds).toEqual([null, "body", "figure-caption"]);
    expect(figure?.children[0]?.tagName).toBe("FIGCAPTION");
  });

  it("names the part it draws inside the figure, title and caption with it", () => {
    render(
      <Figure
        title={null}
        caption="Title set: Malaria gene discovery"
        testId="data-conversation-title"
      >
        {null}
      </Figure>,
    );
    const named = screen.getByTestId("data-conversation-title");
    expect(named).toHaveTextContent("Title set: Malaria gene discovery");
    expect(screen.getByTestId("figure").contains(named)).toBe(true);
    expect(named.querySelectorAll('[data-testid="figure-caption"]')).toHaveLength(1);
  });
});
