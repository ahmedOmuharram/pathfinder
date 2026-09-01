import { describe, expect, it } from "vitest";

import { plotCaption } from "./plotCaptions";

describe("plotCaption", () => {
  it("writes the study and the numbers alone when the model wrote nothing", () => {
    expect(plotCaption("", "Heat shock", "1,543 of 5,511 genes retained")).toBe(
      "Heat shock - 1,543 of 5,511 genes retained.",
    );
  });

  it("writes the numbers alone when there is no study either", () => {
    expect(plotCaption("", "", "6 of 12 Sample, 6 values")).toBe(
      "6 of 12 Sample, 6 values.",
    );
  });

  it("leads with the model's sentence and parenthesizes the facts", () => {
    expect(
      plotCaption(
        "Genes higher in febrile samples than in normal samples",
        "Heat shock",
        "1,543 of 5,511 genes retained",
      ),
    ).toBe(
      "Genes higher in febrile samples than in normal samples (Heat shock - 1,543 of 5,511 genes retained).",
    );
  });

  it("keeps the parentheses when the thread knows no study", () => {
    expect(
      plotCaption("Distribution of temperature", "", "6 of 12 Sample, 6 values"),
    ).toBe("Distribution of temperature (6 of 12 Sample, 6 values).");
  });

  it("drops a period the model already wrote, so the caption ends once", () => {
    expect(plotCaption("Distribution of temperature.", "", "6 of 12 Sample")).toBe(
      "Distribution of temperature (6 of 12 Sample).",
    );
  });

  it("treats a blank caption as no caption", () => {
    expect(plotCaption("   ", "Heat shock", "6 of 12 Sample")).toBe(
      "Heat shock - 6 of 12 Sample.",
    );
  });
});
