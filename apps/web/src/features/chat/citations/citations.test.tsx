// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import type { PathfinderUIMessage } from "@pathfinder/shared";

import { buildCitationIndex } from "./buildIndex";
import { CitationsProvider } from "./CitationsContext";
import { SourcesFooter } from "./SourcesFooter";
import { TextPart } from "../parts/TextPart";
import { SourcePart } from "../parts/SourcePart";

afterEach(() => {
  cleanup();
});

type Parts = PathfinderUIMessage["parts"];

describe("buildCitationIndex", () => {
  it("numbers source-url parts in the order they appear, 1-based", () => {
    const parts: Parts = [
      { type: "text", text: "hello [@a] and [@b]", state: "done" },
      { type: "source-url", sourceId: "a", url: "https://a", title: "A" },
      { type: "source-url", sourceId: "b", url: "https://b" },
    ];
    const index = buildCitationIndex(parts);
    expect(index.entries.map((e) => e.number)).toEqual([1, 2]);
    expect(index.bySourceId.get("a")).toBe(1);
    expect(index.bySourceId.get("b")).toBe(2);
  });

  it("deduplicates by sourceId (first occurrence wins)", () => {
    const parts: Parts = [
      { type: "source-url", sourceId: "a", url: "https://a-first" },
      { type: "source-url", sourceId: "a", url: "https://a-later" },
    ];
    const index = buildCitationIndex(parts);
    expect(index.entries).toHaveLength(1);
    expect(index.entries[0]?.url).toBe("https://a-first");
  });

  it("returns an empty index when there are no source-url parts", () => {
    const parts: Parts = [{ type: "text", text: "hi", state: "done" }];
    const index = buildCitationIndex(parts);
    expect(index.entries).toHaveLength(0);
  });
});

describe("TextPart citation transformation", () => {
  it("rewrites [@sourceId] tokens into numbered [N] links inside a CitationsProvider", () => {
    const index = buildCitationIndex([
      { type: "source-url", sourceId: "strat-42", url: "https://x", title: "X" },
    ]);
    render(
      <CitationsProvider index={index}>
        <TextPart text="Cited source [@strat-42] here." state="done" />
      </CitationsProvider>,
    );
    const link = screen.getByText("[1]");
    expect(link.closest("a")).not.toBeNull();
    expect(link.closest("a")?.getAttribute("href")).toBe("#cite-1");
  });

  it("leaves unknown [@tag] tokens as plain text", () => {
    const index = buildCitationIndex([
      { type: "source-url", sourceId: "known", url: "https://known" },
    ]);
    render(
      <CitationsProvider index={index}>
        <TextPart text="See [@unknown] — not in index." state="done" />
      </CitationsProvider>,
    );
    expect(screen.getByText(/\[@unknown\]/)).toBeTruthy();
  });

  it("does not transform tokens outside a CitationsProvider", () => {
    render(<TextPart text="See [@x] for details." state="done" />);
    expect(screen.getByText(/\[@x\]/)).toBeTruthy();
  });
});

describe("SourcePart with citations context", () => {
  it("renders nothing when inside a CitationsProvider (footer owns visible output)", () => {
    const index = buildCitationIndex([
      { type: "source-url", sourceId: "s", url: "https://s", title: "Src" },
    ]);
    const { container } = render(
      <CitationsProvider index={index}>
        <SourcePart
          part={{ type: "source-url", sourceId: "s", url: "https://s", title: "Src" }}
        />
      </CitationsProvider>,
    );
    expect(container.textContent).toBe("");
  });

  it("falls back to an inline link when no CitationsProvider is present", () => {
    render(
      <SourcePart
        part={{ type: "source-url", sourceId: "s", url: "https://example", title: "Ex" }}
      />,
    );
    const link = screen.getByRole("link", { name: /ex/i });
    expect(link.getAttribute("href")).toBe("https://example");
  });
});

describe("SourcesFooter", () => {
  it("renders a numbered list with id-anchors (cite-1, cite-2, ...)", () => {
    const index = buildCitationIndex([
      { type: "source-url", sourceId: "a", url: "https://a", title: "A" },
      { type: "source-url", sourceId: "b", url: "https://b" },
    ]);
    const { container } = render(<SourcesFooter entries={index.entries} />);
    const items = container.querySelectorAll("li");
    expect(items).toHaveLength(2);
    expect(items[0]?.id).toBe("cite-1");
    expect(items[1]?.id).toBe("cite-2");
  });

  it("returns null when there are no entries", () => {
    const { container } = render(<SourcesFooter entries={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
