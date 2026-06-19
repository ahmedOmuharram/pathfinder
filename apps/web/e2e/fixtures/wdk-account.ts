import { type APIRequestContext, expect } from "@playwright/test";

export interface WdkCreds {
  email: string;
  password: string;
}

// Real VEuPathDB account creds from the environment, or null when unset.
// Credentialed WDK tests skip by default and run only when both are provided.
export function wdkAccountCreds(): WdkCreds | null {
  const email = process.env["WDK_TEST_EMAIL"];
  const password = process.env["WDK_TEST_PASSWORD"];
  return email != null && password != null && email !== "" && password !== ""
    ? { email, password }
    : null;
}

export async function loginWdkAccount(
  apiClient: APIRequestContext,
  creds: WdkCreds,
  siteId: string,
): Promise<void> {
  const resp = await apiClient.post("/api/v1/veupathdb/auth/login", {
    params: { siteId },
    data: creds,
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  expect(resp.ok(), `wdk login ${resp.status()}: ${await resp.text()}`).toBeTruthy();
}
