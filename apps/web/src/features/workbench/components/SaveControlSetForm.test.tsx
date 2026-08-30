// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockCreateControlSet = vi.fn();
vi.mock("../api/controlSets", () => ({
  createControlSet: (...args: unknown[]) => mockCreateControlSet(...args),
}));

import { SaveControlSetForm } from "./SaveControlSetForm";

describe("SaveControlSetForm", () => {
  afterEach(() => {
    cleanup();
    mockCreateControlSet.mockReset();
  });

  it("shows save button that expands the form", () => {
    render(
      <SaveControlSetForm
        siteId="PlasmoDB"
        positiveIds={["PF3D7_0100100"]}
        negativeIds={[]}
      />,
    );
    fireEvent.click(screen.getByText(/Save as Control Set/));
    expect(screen.getByPlaceholderText("Control set name")).toBeTruthy();
  });

  it("is disabled when no positive IDs", () => {
    render(<SaveControlSetForm siteId="PlasmoDB" positiveIds={[]} negativeIds={[]} />);
    const btn = screen.getByText(/Save as Control Set/).closest("button");
    expect(btn?.hasAttribute("disabled")).toBe(true);
  });

  it("calls createControlSet with correct payload on save", async () => {
    mockCreateControlSet.mockResolvedValue({ id: "cs-new", name: "Test" });
    render(
      <SaveControlSetForm
        siteId="PlasmoDB"
        positiveIds={["PF3D7_0100100", "PF3D7_0200200"]}
        negativeIds={["PF3D7_0900900"]}
      />,
    );
    fireEvent.click(screen.getByText(/Save as Control Set/));
    fireEvent.change(screen.getByPlaceholderText("Control set name"), {
      target: { value: "My controls" },
    });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(mockCreateControlSet).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "My controls",
          siteId: "PlasmoDB",
          positiveIds: ["PF3D7_0100100", "PF3D7_0200200"],
          negativeIds: ["PF3D7_0900900"],
        }),
      );
    });
  });

  it("confirms the save with the success token", async () => {
    mockCreateControlSet.mockResolvedValue({ id: "cs-new", name: "Test" });
    render(
      <SaveControlSetForm
        siteId="PlasmoDB"
        positiveIds={["PF3D7_0100100"]}
        negativeIds={[]}
      />,
    );
    fireEvent.click(screen.getByText(/Save as Control Set/));
    fireEvent.change(screen.getByPlaceholderText("Control set name"), {
      target: { value: "My controls" },
    });
    fireEvent.click(screen.getByText("Save"));

    const confirmation = await screen.findByText("Control set saved!");
    expect(confirmation).toHaveClass("text-success");
    expect(confirmation.className).not.toContain("green-");
    expect(confirmation.className).not.toContain("dark:");
  });

  it("collapses form on cancel", () => {
    render(
      <SaveControlSetForm
        siteId="PlasmoDB"
        positiveIds={["PF3D7_0100100"]}
        negativeIds={[]}
      />,
    );
    fireEvent.click(screen.getByText(/Save as Control Set/));
    expect(screen.getByPlaceholderText("Control set name")).toBeTruthy();
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByPlaceholderText("Control set name")).toBeNull();
  });
});
