import { test, expect } from "@playwright/test";
import { gotoHomeWithStrategy, sendMessage } from "./helpers";

test("execute: can apply a deterministic planning artifact to strategy", async ({
  page,
}) => {
  await gotoHomeWithStrategy(page);

  // Trigger mock provider to emit a planning artifact (see API mock stream).
  await sendMessage(page, "please emit artifact");

  // Wait for the mock execute-mode response to complete before looking for
  // the artifact section — under parallel load the API can be slow, and
  // other tests' plan-mode messages may also contain artifact headings.
  await expect(page.getByText("[mock:execute]").first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("Saved planning artifacts").first()).toBeVisible();
  const apply = page.getByRole("button", { name: "Apply to strategy" }).first();
  await expect(apply).toBeVisible();

  const patchReq = page.waitForRequest((req) => {
    return req.method() === "PATCH" && req.url().includes("/api/v1/strategies/");
  });
  await apply.click();

  const req = await patchReq;
  const body = req.postDataJSON() as Record<string, unknown>;
  expect(body).toHaveProperty("plan");
  expect(
    (body.plan as Record<string, unknown>)?.root as Record<string, unknown>,
  ).toHaveProperty("searchName", "mock_search");
});
