import { expect, type Page } from "@playwright/test";

export async function gotoHome(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("message-composer")).toBeVisible();
}

export async function switchToPlan(page: Page) {
  await page.getByTestId("mode-toggle-plan").click();
  await expect(page.getByTestId("mode-toggle-plan")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
}

export async function switchToExecute(page: Page) {
  await page.getByTestId("mode-toggle-execute").click();
  await expect(page.getByTestId("mode-toggle-execute")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
}

export async function sendMessage(page: Page, message: string) {
  await page.getByTestId("message-input").fill(message);
  await page.getByTestId("send-button").click();
}

export async function switchToGraphView(page: Page) {
  const chatPreview = page.getByRole("button", { name: /chat preview/i }).first();
  if (await chatPreview.isVisible()) return;

  // The preview widget is a div with role=button, labeled "Graph preview" when chat is active.
  const graphPreview = page.getByRole("button", { name: /graph preview/i }).first();
  await expect(graphPreview).toBeVisible();
  await graphPreview.click();
  await expect(chatPreview).toBeVisible({ timeout: 20_000 });
}

export async function switchToChatView(page: Page) {
  const composer = page.getByTestId("message-composer");
  const graphPreview = page.getByRole("button", { name: /graph preview/i }).first();
  if (await graphPreview.isVisible()) return;
  const chatPreview = page.getByRole("button", { name: /chat preview/i }).first();
  await expect(chatPreview).toBeVisible();
  await chatPreview.click();
  await expect(graphPreview).toBeVisible({ timeout: 20_000 });
  await expect(composer).toBeVisible();
}

export async function expectIdleComposer(page: Page) {
  await expect(page.getByTestId("send-button")).toBeVisible();
}

export async function expectStreaming(page: Page) {
  await expect(page.getByTestId("stop-button")).toBeVisible();
}
