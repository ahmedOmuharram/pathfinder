// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { VerificationResults } from "./VerificationResults";

describe("VerificationResults", () => {
  it("counts valid genes through the success token", () => {
    render(
      <VerificationResults
        resolvedGenes={[
          {
            geneId: "PF3D7_0100100",
            displayName: "PF3D7_0100100",
            organism: "Plasmodium falciparum 3D7",
            product: "real gene",
            geneName: "",
            geneType: "",
            location: "",
          },
        ]}
        unresolvedIds={["NOT_A_GENE"]}
      />,
    );
    const valid = screen.getByText(/1 valid/);
    expect(valid).toHaveClass("text-success");
    expect(valid.className).not.toContain("green-");
    expect(valid.className).not.toContain("dark:");
    expect(screen.getByText(/1 not found/)).toHaveClass("text-destructive");
  });
});
