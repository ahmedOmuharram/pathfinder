// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { stepMetaSchema } from "./stepMetaSchema";

describe("stepMetaSchema", () => {
  it("accepts valid name", () => {
    expect(stepMetaSchema.safeParse({ name: "My Step", description: "" }).success).toBe(true);
  });

  it("rejects empty name", () => {
    expect(stepMetaSchema.safeParse({ name: "", description: "" }).success).toBe(false);
  });

  it("rejects whitespace-only name", () => {
    expect(stepMetaSchema.safeParse({ name: "   ", description: "" }).success).toBe(false);
  });

  it("accepts empty description", () => {
    expect(stepMetaSchema.safeParse({ name: "Step", description: "" }).success).toBe(true);
  });

  it("requires description field", () => {
    expect(stepMetaSchema.safeParse({ name: "Step" }).success).toBe(false);
  });

  it("trims name whitespace", () => {
    const result = stepMetaSchema.safeParse({ name: "  My Step  ", description: "" });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.name).toBe("My Step");
    }
  });
});
