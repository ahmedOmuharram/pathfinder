import { test, expect } from "@playwright/test";
import { gotoHomeWithStrategy, sendMessage } from "./helpers";

test("execute: can apply a deterministic planning artifact to strategy", async ({
  page,
}) => {
  await gotoHomeWithStrategy(page);

  // Trigger mock provider to emit a planning artifact (see API mock stream).
  await sendMessage(page, "please emit artifact");

  await expect(page.getByText("Saved planning artifacts")).toBeVisible();
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
