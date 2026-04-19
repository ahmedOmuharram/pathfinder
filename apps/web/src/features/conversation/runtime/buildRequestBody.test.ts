import { describe, it, expect } from "vitest";

import { buildChatRequestBody } from "./buildRequestBody";

describe("buildChatRequestBody", () => {
  it("throws if siteId is empty", () => {
    expect(() =>
      buildChatRequestBody({
        conversationId: "c1",
        siteId: "",
        id: "x",
        trigger: "submit-message",
        messages: [],
        baseBody: undefined,
      }),
    ).toThrow(/siteId is required/);
  });

  it("throws if siteId is whitespace only", () => {
    expect(() =>
      buildChatRequestBody({
        conversationId: "c1",
        siteId: "   ",
        id: "x",
        trigger: "submit-message",
        messages: [],
        baseBody: undefined,
      }),
    ).toThrow();
  });

  it("includes siteId, conversationId, id, trigger, messages when siteId is set", () => {
    const out = buildChatRequestBody({
      conversationId: "c1",
      siteId: "plasmodb",
      id: "x",
      trigger: "submit-message",
      messages: [],
      baseBody: undefined,
    });
    expect(out).toMatchObject({
      conversationId: "c1",
      siteId: "plasmodb",
      id: "x",
      trigger: "submit-message",
      messages: [],
    });
  });

  it("merges base body fields under our overrides", () => {
    const out = buildChatRequestBody({
      conversationId: "c1",
      siteId: "plasmodb",
      id: "x",
      trigger: "submit-message",
      messages: [],
      baseBody: { extra: "passthrough", conversationId: "should-be-overridden" },
    });
    expect(out["extra"]).toBe("passthrough");
    expect(out.conversationId).toBe("c1");
  });
});
