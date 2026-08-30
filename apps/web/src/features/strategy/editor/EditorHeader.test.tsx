// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Step, StepKind } from "@pathfinder/shared";
import { EditorHeader } from "./EditorHeader";

const STEP: Step = {
  id: "s1",
  kind: "search",
  displayName: "Genes by taxon",
  searchName: "GenesByTaxon",
  recordType: "gene",
  parameters: {},
  isFiltered: false,
};

function renderHeader(kind: StepKind) {
  return render(
    <EditorHeader
      step={STEP}
      kind={kind}
      stepNumber={1}
      onRename={() => {}}
      onDelete={() => {}}
      onDuplicate={() => {}}
      onCopyUrl={() => {}}
      onSaveAsReusable={() => {}}
    />,
  );
}

describe("EditorHeader kind badge", () => {
  it("tints the search badge from the leaf kind token", () => {
    renderHeader("search");
    expect(screen.getByText("search")).toHaveClass(
      "bg-[hsl(var(--kind-leaf)/0.15)]",
      "text-foreground",
    );
  });

  it("tints the combine badge from the combine kind token", () => {
    renderHeader("combine");
    expect(screen.getByText("combine")).toHaveClass(
      "bg-[hsl(var(--kind-combine)/0.15)]",
      "text-foreground",
    );
  });

  it("tints the transform badge from the transform kind token", () => {
    renderHeader("transform");
    expect(screen.getByText("transform")).toHaveClass(
      "bg-[hsl(var(--kind-transform)/0.15)]",
      "text-foreground",
    );
  });
});
