import { test, expect } from "@playwright/test";

test("health is ok", async ({ request }) => {
  const res = await request.get("/health");
  expect(res.ok()).toBeTruthy();
});
