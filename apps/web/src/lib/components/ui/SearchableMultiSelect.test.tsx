// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { afterEach } from "vitest";

import { SearchableMultiSelect } from "./SearchableMultiSelect";

const OPTIONS = [
  { value: "pf3d7", label: "Plasmodium falciparum 3D7" },
  { value: "pvivax", label: "Plasmodium vivax" },
  { value: "pberghei", label: "Plasmodium berghei" },
  { value: "tgondii", label: "Toxoplasma gondii" },
];

afterEach(cleanup);

describe("SearchableMultiSelect", () => {
  it("renders placeholder when nothing selected", () => {
    render(
      <SearchableMultiSelect
        options={OPTIONS}
        selected={[]}
        onChange={() => {}}
        placeholder="Select organisms"
      />,
    );
    expect(screen.getByText("Select organisms")).toBeTruthy();
  });

  it("opens dropdown on click and shows all options", () => {
    render(
      <SearchableMultiSelect options={OPTIONS} selected={[]} onChange={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Plasmodium falciparum 3D7")).toBeTruthy();
    expect(screen.getByText("Toxoplasma gondii")).toBeTruthy();
  });

  it("filters options by search text", () => {
    render(
      <SearchableMultiSelect options={OPTIONS} selected={[]} onChange={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button"));
    const search = screen.getByPlaceholderText("Search...");
    fireEvent.change(search, { target: { value: "vivax" } });
    expect(screen.getByText("Plasmodium vivax")).toBeTruthy();
    expect(screen.queryByText("Toxoplasma gondii")).toBeNull();
  });

  it("calls onChange when option is toggled on", () => {
    const onChange = vi.fn();
    render(
      <SearchableMultiSelect options={OPTIONS} selected={[]} onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(screen.getByText("Plasmodium vivax"));
    expect(onChange).toHaveBeenCalledWith(["pvivax"]);
  });

  it("calls onChange when option is toggled off", () => {
    const onChange = vi.fn();
    render(
      <SearchableMultiSelect
        options={OPTIONS}
        selected={["pvivax", "pf3d7"]}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByLabelText("Toggle dropdown"));
    fireEvent.click(screen.getAllByText("Plasmodium vivax")[0]!);
    expect(onChange).toHaveBeenCalledWith(["pf3d7"]);
  });

  it("shows selected items as chips", () => {
    render(
      <SearchableMultiSelect
        options={OPTIONS}
        selected={["pf3d7", "pvivax"]}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText("Plasmodium falciparum 3D7")).toBeTruthy();
    expect(screen.getByText("Plasmodium vivax")).toBeTruthy();
  });

  it("removes chip on X click", () => {
    const onChange = vi.fn();
    render(
      <SearchableMultiSelect
        options={OPTIONS}
        selected={["pf3d7"]}
        onChange={onChange}
      />,
    );
    const removeButtons = screen
      .getAllByRole("button")
      .filter((b) => b.getAttribute("aria-label")?.includes("Remove"));
    fireEvent.click(removeButtons[0]!);
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("shows loading spinner when loading", () => {
    render(
      <SearchableMultiSelect options={[]} selected={[]} onChange={() => {}} loading />,
    );
    expect(screen.getByText(/loading/i)).toBeTruthy();
  });

  it("closes dropdown on Escape", () => {
    render(
      <SearchableMultiSelect options={OPTIONS} selected={[]} onChange={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Plasmodium falciparum 3D7")).toBeTruthy();
    const search = screen.getByPlaceholderText("Search...");
    fireEvent.keyDown(search, { key: "Escape" });
    expect(screen.queryByText("Plasmodium falciparum 3D7")).toBeNull();
  });

  it("shows checkmarks next to selected options", () => {
    render(
      <SearchableMultiSelect
        options={OPTIONS}
        selected={["pf3d7"]}
        onChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText("Toggle dropdown"));
    const option = screen
      .getAllByText("Plasmodium falciparum 3D7")[0]!
      .closest("button");
    expect(option?.querySelector("[data-checked]")).toBeTruthy();
  });
});
