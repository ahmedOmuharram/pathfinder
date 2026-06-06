import { describe, expect, it } from "vitest";
import { chatRoot, chatUrl, workbenchGeneSetUrl, workbenchRoot } from "./routes";

describe("route builders", () => {
  it("prefix every target with the site id", () => {
    expect(chatRoot("plasmodb")).toBe("/plasmodb/conversation");
    expect(chatUrl("plasmodb", "c1")).toBe("/plasmodb/conversation/c1");
    expect(workbenchRoot("toxodb")).toBe("/toxodb/workbench");
    expect(workbenchGeneSetUrl("toxodb", "g1")).toBe("/toxodb/workbench/g1");
  });
});
