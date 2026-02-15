import type {
  SearchValidationPayload,
  SearchValidationResponse,
} from "@pathfinder/shared";

export function formatSearchValidationResponse(
  response: SearchValidationResponse | null | undefined,
): { message: string | null; keys: Set<string> } {
  const payload: SearchValidationPayload | null | undefined = response?.validation;
  if (!payload || payload.isValid !== false) return { message: null, keys: new Set() };

  const general = payload.errors?.general || [];
  const byKey = payload.errors?.byKey || {};

  const parts: string[] = [];
  if (general.length > 0) parts.push(...general);

  const keys = new Set<string>();
  for (const [key, messages] of Object.entries(byKey)) {
    if (!messages || messages.length === 0) continue;
    keys.add(key);
    parts.push(`${key}: ${messages.join(", ")}`);
  }

  const message =
    parts.length > 0
      ? `Cannot be saved: ${parts.join("; ")}`
      : "Cannot be saved: parameters do not match the spec.";

  return { message, keys };
}
