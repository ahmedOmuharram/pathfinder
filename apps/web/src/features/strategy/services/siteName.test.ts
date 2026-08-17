import { describe, expect, it } from "vitest";
import { siteDisplayName, siteShortName } from "@pathfinder/shared";

describe("siteShortName", () => {
  // A button reads "View in PlasmoDB". The long form carries the organism in
  // parentheses, which belongs in a picker rather than on a link.
  it("gives the brand name, not the long form", () => {
    expect(siteShortName("plasmodb")).toBe("PlasmoDB");
  });

  it("names the portal", () => {
    expect(siteShortName("veupathdb")).toBe("VEuPathDB");
  });

  it("is shorter than the long form for a component site", () => {
    expect(siteShortName("toxodb").length).toBeLessThan(
      siteDisplayName("toxodb").length,
    );
  });

  it("falls back to the id for a site it does not know", () => {
    expect(siteShortName("notasite")).toBe("notasite");
  });

  it("falls back to the id for an empty site", () => {
    expect(siteShortName("")).toBe("");
  });

  it("leaves the long form alone", () => {
    expect(siteDisplayName("plasmodb")).toBe("PlasmoDB (Plasmodium)");
  });
});
