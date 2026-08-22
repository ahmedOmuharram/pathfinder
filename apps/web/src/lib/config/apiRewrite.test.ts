import { describe, expect, it } from "vitest";

import nextConfig from "../../../next.config";

/**
 * The browser reaches the API through the `/api/:path*` rewrite. Next caps a
 * rewrite at 30 s by default and answers its own bare 500, so an API call that
 * legitimately runs longer (a data purge that also deletes WDK strategies)
 * never returns its result to the caller.
 */
describe("API rewrite", () => {
  it("gives a long API call more than Next's 30 s default", () => {
    const timeout = nextConfig.experimental?.proxyTimeout;
    expect(timeout).toBeDefined();
    expect(timeout).toBeGreaterThan(30_000);
  });
});
