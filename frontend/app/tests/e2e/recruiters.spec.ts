import { test, expect } from "@playwright/test";

test.describe("/app/recruiters", () => {
  test("renders recruiter cards", async ({ page }) => {
    await page.goto("/app/recruiters");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    await expect(page.getByRole("heading", { name: "Рекрутёры", exact: false })).toBeVisible({ timeout: 10000 });

    // Check for cards or empty state
    const row = page.getByTestId("recruiter-row").first();
    const empty = page.getByText("Реестр рекрутёров пока пуст");
    await expect(row.or(empty)).toBeVisible({ timeout: 10000 });
  });

  test("can navigate to new recruiter form", async ({ page }) => {
    await page.goto("/app/recruiters");
    await page.waitForLoadState("domcontentloaded");

    const newButton = page.getByTestId("recruiters-create-btn");
    await expect(newButton).toBeVisible({ timeout: 10000 });
    await newButton.click();
    await page.waitForURL("/app/recruiters/new");
  });

  test("new recruiter form has city selection", async ({ page }) => {
    await page.goto("/app/recruiters/new");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    // Check for city selection tiles/checkboxes
    await expect(page.getByTestId("recruiter-city-selection")).toBeVisible({ timeout: 10000 });
  });
});
