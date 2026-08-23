import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import captured from "../../src/protocol/captured.json" with { type: "json" };
import { extractProtocol } from "../../src/protocol/extract.ts";

const PROTOCOL_PATH = fileURLToPath(
  new URL("../../../assistant-core/PROTOCOL.md", import.meta.url),
);

describe("the vendored protocol capture", () => {
  it("is what PROTOCOL.md says, byte for byte", () => {
    const source = readFileSync(PROTOCOL_PATH, "utf8");

    expect(extractProtocol(source)).toEqual(captured);
  });

  it("names the protocol version the document declares", () => {
    expect(captured.version).toBe("1.0.0");
  });

  it("carries one example per kind the reference assistant produces", () => {
    expect(captured.examples).toHaveLength(18);
    const kinds = captured.examples.map((example) => example.kind);
    expect(new Set(kinds).size).toBe(kinds.length);
  });
});
