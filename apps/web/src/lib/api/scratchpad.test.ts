import { describe, expect, it } from "vitest";

import {
  scratchpadNotesOptions,
  scratchpadCompactionsOptions,
} from "./scratchpad";

describe("scratchpad query options", () => {
  it("produces stable keys", () => {
    const conv = "11111111-2222-3333-4444-555555555555";
    expect(scratchpadNotesOptions(conv).queryKey).toEqual([
      "conversations",
      conv,
      "scratchpad",
      "notes",
    ]);
    expect(scratchpadCompactionsOptions(conv).queryKey).toEqual([
      "conversations",
      conv,
      "scratchpad",
      "compactions",
    ]);
  });
});
