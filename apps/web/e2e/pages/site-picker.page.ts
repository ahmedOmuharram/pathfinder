import { type Locator, type Page, expect } from "@playwright/test";

export class SitePickerComponent {
  readonly select: Locator;
  readonly switcherTrigger: Locator;

  constructor(private page: Page) {
    this.select = page.getByTestId("site-select");
    this.switcherTrigger = page.getByRole("button", { name: /switch database/i });
  }

  async selectSite(siteId: string) {
    if (await this.switcherTrigger.isVisible().catch(() => false)) {
      await this.switcherTrigger.click();
      await this.page.getByTestId(`site-menu-item-${siteId}`).click();
      return;
    }
    await this.select.selectOption(siteId);
  }

  async confirmSwitch() {
    await this.page.getByRole("button", { name: /switch site/i }).click();
  }

  async cancelSwitch() {
    await this.page.getByRole("button", { name: /cancel/i }).click();
  }

  async expectCurrentSite(siteId: string) {
    await expect(this.select).toHaveValue(siteId);
  }
}
