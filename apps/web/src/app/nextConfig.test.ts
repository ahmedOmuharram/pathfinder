import { describe, expect, it } from "vitest";

import nextConfig from "../../next.config";

/**
 * The dev-tools indicator button renders in a page corner and takes the
 * pointer events of anything under it.
 */
describe("the Next config", () => {
  it("ships no dev-tools indicator", () => {
    expect(nextConfig.devIndicators).toBe(false);
  });
});
