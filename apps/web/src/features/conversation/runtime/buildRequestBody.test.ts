import { describe, it, expect } from "vitest";

import { buildChatRequestBody } from "./buildRequestBody";

describe("buildChatRequestBody", () => {
  it("throws if siteId is empty", () => {
    expect(() =>
      buildChatRequestBody({
        chatId: "c1",
        siteId: "",
        id: "x",
        trigger: "submit-message",
        messages: [],
        parentCheckpointId: null,
        baseBody: undefined,
      }),
    ).toThrow(/siteId is required/);
  });

  it("throws if siteId is whitespace only", () => {
    expect(() =>
      buildChatRequestBody({
        chatId: "c1",
        siteId: "   ",
        id: "x",
        trigger: "submit-message",
        messages: [],
        parentCheckpointId: null,
        baseBody: undefined,
      }),
    ).toThrow();
  });

  it("includes siteId, chatId, id, trigger, messages when siteId is set", () => {
    const out = buildChatRequestBody({
      chatId: "c1",
      siteId: "plasmodb",
      id: "x",
      trigger: "submit-message",
      messages: [],
      parentCheckpointId: null,
      baseBody: undefined,
    });
    expect(out).toMatchObject({
      chatId: "c1",
      siteId: "plasmodb",
      id: "x",
      trigger: "submit-message",
      messages: [],
    });
    expect(out).not.toHaveProperty("parentCheckpointId");
  });

  it("includes parentCheckpointId when provided", () => {
    const out = buildChatRequestBody({
      chatId: "c1",
      siteId: "plasmodb",
      id: "x",
      trigger: "submit-message",
      messages: [],
      parentCheckpointId: "cp-42",
      baseBody: undefined,
    });
    expect(out.parentCheckpointId).toBe("cp-42");
  });

  it("merges base body fields under our overrides", () => {
    const out = buildChatRequestBody({
      chatId: "c1",
      siteId: "plasmodb",
      id: "x",
      trigger: "submit-message",
      messages: [],
      parentCheckpointId: null,
      baseBody: { extra: "passthrough", chatId: "should-be-overridden" },
    });
    expect(out["extra"]).toBe("passthrough");
    expect(out.chatId).toBe("c1");
  });
});
