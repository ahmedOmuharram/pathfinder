import { describe, expect, it } from "vitest";
import { decodeNodeSelection, encodeNodeSelection, normalizeNodeSelection } from "./node_selection";

describe("node_selection", () => {
  it("round-trips selection + message", () => {
    const selection = { graphId: "g1", nodeIds: ["a", "b"], selectedNodeIds: ["b"] };
    const msg = "Hello";
    const encoded = encodeNodeSelection(selection, msg);
    const decoded = decodeNodeSelection(encoded);
    expect(decoded.message).toBe(msg);
    expect(decoded.selection).toEqual(normalizeNodeSelection(selection));
  });

  it("decodes message with no selection", () => {
    const decoded = decodeNodeSelection("Just text");
    expect(decoded.message).toBe("Just text");
    expect(decoded.selection).toBeNull();
  });
});

