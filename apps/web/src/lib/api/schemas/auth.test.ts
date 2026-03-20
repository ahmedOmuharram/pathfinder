import { describe, expect, it } from "vitest";
import { AuthStatusResponseSchema, AuthSuccessResponseSchema } from "./auth";

describe("AuthStatusResponseSchema", () => {
  it("parses a signed-in response", () => {
    const result = AuthStatusResponseSchema.safeParse({
      signedIn: true,
      name: "Alice",
      email: "alice@example.com",
    });
    expect(result.success).toBe(true);
    expect(result.data?.signedIn).toBe(true);
    expect(result.data?.name).toBe("Alice");
  });

  it("parses a signed-out response with null name/email", () => {
    const result = AuthStatusResponseSchema.safeParse({
      signedIn: false,
      name: null,
      email: null,
    });
    expect(result.success).toBe(true);
    expect(result.data?.signedIn).toBe(false);
    expect(result.data?.name).toBeNull();
  });

  it("passes through extra fields", () => {
    const result = AuthStatusResponseSchema.safeParse({
      signedIn: true,
      name: "Alice",
      email: "alice@example.com",
      role: "admin",
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>)["role"]).toBe("admin");
  });

  it("rejects missing signedIn field", () => {
    const result = AuthStatusResponseSchema.safeParse({
      name: "Alice",
      email: "alice@example.com",
    });
    expect(result.success).toBe(false);
  });
});

describe("AuthSuccessResponseSchema", () => {
  it("parses a success response", () => {
    const result = AuthSuccessResponseSchema.safeParse({ success: true });
    expect(result.success).toBe(true);
    expect(result.data?.success).toBe(true);
  });

  it("parses a failure response", () => {
    const result = AuthSuccessResponseSchema.safeParse({ success: false });
    expect(result.success).toBe(true);
    expect(result.data?.success).toBe(false);
  });

  it("passes through extra fields", () => {
    const result = AuthSuccessResponseSchema.safeParse({
      success: true,
      message: "Logged in",
    });
    expect(result.success).toBe(true);
    expect((result.data as Record<string, unknown>)["message"]).toBe("Logged in");
  });

  it("rejects missing success field", () => {
    const result = AuthSuccessResponseSchema.safeParse({});
    expect(result.success).toBe(false);
  });
});
