// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Step } from "@pathfinder/shared";

import { HoverActions } from "./HoverActions";

function makeStep(overrides: Partial<Step> = {}): Step {
  return {
    id: "s1",
    kind: "search",
    displayName: "Genes by taxon",
    searchName: "GenesByTaxon",
    recordType: "gene",
    parameters: {},
    estimatedSize: 100,
    isFiltered: false,
    validation: null,
    ...overrides,
  };
}

afterEach(cleanup);

describe("HoverActions delete affordance", () => {
  it("the kebab 'Delete step' invokes onDelete once with the exact step id", async () => {
    const onDelete = vi.fn();
    render(
      <HoverActions step={makeStep({ id: "interpro_or_go" })} onDelete={onDelete} />,
    );

    await userEvent.click(screen.getByTestId("rf-more-interpro_or_go"));
    await userEvent.click(
      await screen.findByRole("menuitem", { name: /delete step/i }),
    );

    expect(onDelete.mock.calls).toEqual([["interpro_or_go"]]);
  });

  it("the kebab 'Duplicate step' invokes onDuplicate once with the exact step id", async () => {
    const onDuplicate = vi.fn();
    render(
      <HoverActions
        step={makeStep({ id: "interpro_kinases" })}
        onDuplicate={onDuplicate}
      />,
    );

    await userEvent.click(screen.getByTestId("rf-more-interpro_kinases"));
    await userEvent.click(
      await screen.findByRole("menuitem", { name: /duplicate step/i }),
    );

    expect(onDuplicate.mock.calls).toEqual([["interpro_kinases"]]);
  });

  it("offers no destructive action when its handlers are unwired", async () => {
    render(<HoverActions step={makeStep({ id: "s2" })} />);
    await userEvent.click(screen.getByTestId("rf-more-s2"));
    const labels = (await screen.findAllByRole("menuitem")).map((el) =>
      el.textContent.trim(),
    );
    expect(labels).toContain("Copy step ID");
    expect(labels).not.toContain("Delete step");
    expect(labels).not.toContain("Duplicate step");
  });

  it("nests the kebab inside the toolbar the onNodeClick guard keys on", () => {
    render(<HoverActions step={makeStep({ id: "s3" })} onDelete={vi.fn()} />);
    const kebab = screen.getByTestId("rf-more-s3");
    expect(kebab.closest("[data-node-toolbar]")).not.toBe(null);
  });
});
