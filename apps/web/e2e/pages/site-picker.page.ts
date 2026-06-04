import { type Locator, type Page, expect } from "@playwright/test";

export class SitePickerComponent {
  readonly switcherTrigger: Locator;

  constructor(private page: Page) {
    this.switcherTrigger = page.getByRole("button", { name: /switch database/i });
  }

  async selectSite(siteId: string) {
    await this.switcherTrigger.click();
    await this.page.getByTestId(`site-menu-item-${siteId}`).click();
  }

  async confirmSwitch() {
    await this.page.getByRole("button", { name: /switch site/i }).click();
  }

  async cancelSwitch() {
    await this.page.getByRole("button", { name: /cancel/i }).click();
  }

  async expectCurrentSite(siteId: string) {
    // The active site lives in the URL (`/{siteId}/...`) now, not a <select>.
    await expect(this.page).toHaveURL(new RegExp(`/${siteId}(/|$)`));
  }
}
