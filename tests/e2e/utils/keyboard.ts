import { Page } from "@playwright/test";

export async function pressTab(page: Page, count = 1) {
  for (let i = 0; i < count; i++) await page.keyboard.press("Tab");
}
export async function pressShiftTab(page: Page, count = 1) {
  for (let i = 0; i < count; i++) await page.keyboard.down("Shift"), await page.keyboard.press("Tab"), await page.keyboard.up("Shift");
}
export async function pressEsc(page: Page) {
  await page.keyboard.press("Escape");
}
