import { test, expect, type Page } from "@playwright/test";

// Next 16 blocks its dev resources for the 127.0.0.1 host, so client bundles never hydrate there;
// localhost reaches the same server on port 3100 and keeps the checks against the real hydrated app.
test.use({ baseURL: "http://localhost:3100" });

interface PageTarget {
  path: string;
  heading: string;
}

const PAGES: readonly PageTarget[] = [
  { path: "/", heading: "ShootingStar" },
  { path: "/about", heading: "ShootingStar: Nghiên cứu dự đoán 30 phút" },
  { path: "/dashboard", heading: "Tổng quan" },
  { path: "/data", heading: "Lịch sử giá" },
  { path: "/replay", heading: "Mô phỏng" },
  { path: "/report", heading: "Báo cáo" },
];

/** Collects browser console errors and uncaught page errors for the current page. */
function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  return errors;
}

test.describe("page smoke", () => {
  test.setTimeout(90_000);

  for (const target of PAGES) {
    test(`opens ${target.path} with a heading and no client errors`, async ({ page }) => {
      const errors = collectErrors(page);

      const response = await page.goto(target.path);
      expect(response?.status()).toBe(200);

      await expect(page.getByRole("heading", { level: 1, name: target.heading })).toBeVisible();
      await expect(page.locator("body")).not.toContainText("fetch failed");

      // Let late client-side effects (client components, dev overlay) finish before judging the console.
      await page.waitForTimeout(1_000);
      expect(errors).toEqual([]);
    });
  }
});
