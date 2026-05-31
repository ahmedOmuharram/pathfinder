/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import type { Search } from "@pathfinder/shared";
import { SearchPicker } from "./SearchPicker";

afterEach(cleanup);

const SEARCHES: Search[] = [
  {
    name: "GenesByMolecularWeight",
    displayName: "Genes by molecular weight",
    recordType: "transcript",
    description: "",
  },
  {
    name: "GenesByTextSearch",
    displayName: "Genes by text search",
    recordType: "transcript",
    description: "",
  },
  {
    name: "GeneListByGo",
    displayName: "Genes by GO term",
    recordType: "transcript",
    description: "",
  },
  {
    name: "PathwayByName",
    displayName: "Pathway by name",
    recordType: "pathway",
    description: "",
  },
];

describe("SearchPicker", () => {
  it("opens the picker on trigger click", async () => {
    const user = userEvent.setup();
    render(<SearchPicker searches={SEARCHES} value={null} onChange={() => {}} />);
    await user.click(screen.getByRole("combobox"));
    expect(screen.getByText("Genes by molecular weight")).toBeTruthy();
  });

  it("filters by typed query", async () => {
    const user = userEvent.setup();
    render(<SearchPicker searches={SEARCHES} value={null} onChange={() => {}} />);
    await user.click(screen.getByRole("combobox"));
    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "molec");
    expect(screen.getByText("Genes by molecular weight")).toBeTruthy();
    expect(screen.queryByText("Pathway by name")).toBeNull();
  });

  it("groups by record type", async () => {
    const user = userEvent.setup();
    render(<SearchPicker searches={SEARCHES} value={null} onChange={() => {}} />);
    await user.click(screen.getByRole("combobox"));
    expect(screen.getByText("transcript")).toBeTruthy();
    expect(screen.getByText("pathway")).toBeTruthy();
  });

  it("fires onChange with the picked search name", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SearchPicker searches={SEARCHES} value={null} onChange={onChange} />);
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByText("Pathway by name"));
    expect(onChange).toHaveBeenCalledWith("PathwayByName");
  });

  it("renders the selected search label when a value is picked", () => {
    render(
      <SearchPicker
        searches={SEARCHES}
        value="GenesByMolecularWeight"
        onChange={() => {}}
      />,
    );
    expect(screen.getByText("Genes by molecular weight")).toBeTruthy();
  });
});
