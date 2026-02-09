export type AppErrorCode = "INVARIANT_VIOLATION" | "SERIALIZE_FAILED" | "UNKNOWN";

/**
 * A typed, application-level error for client-side failures that are not API errors.
 * Use this instead of `new Error()` so UI messaging is consistent and testable.
 */
export class AppError extends Error {
  code: AppErrorCode;

  constructor(message: string, code: AppErrorCode = "UNKNOWN") {
    super(message);
    this.name = "AppError";
    this.code = code;
  }
}
