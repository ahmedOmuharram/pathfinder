import { describe, expect, it } from "vitest";
import { AppError } from "./AppError";

describe("AppError", () => {
  it("defaults the code to UNKNOWN and tags the error name", () => {
    const err = new AppError("boom");
    expect(err).toBeInstanceOf(Error);
    expect(err.message).toBe("boom");
    expect(err.code).toBe("UNKNOWN");
    expect(err.name).toBe("AppError");
  });

  it("carries the provided code", () => {
    const err = new AppError("bad invariant", "INVARIANT_VIOLATION");
    expect(err.code).toBe("INVARIANT_VIOLATION");
    expect(err.message).toBe("bad invariant");
  });
});
