import { test, expect, type Page } from "@playwright/test";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

// Next 16 blocks its dev resources for the 127.0.0.1 host, so client bundles never hydrate there;
// localhost reaches the same server on port 3100 and keeps the checks against the real hydrated app.
test.use({ baseURL: "http://localhost:3100" });

const SNAPSHOT_ID = process.env.E2E_SNAPSHOT_ID ?? "";
const SHORT_ID = SNAPSHOT_ID.slice(0, 8);
const MID_WINDOW_INPUT = "2026-10-30T12:00";

function recordJob(entry: Record<string, string>): void {
  const file = path.resolve(process.cwd(), "e2e", ".created-jobs.json");
  const existing: unknown = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : [];
  const entries = Array.isArray(existing) ? (existing as Record<string, string>[]) : [];
  entries.push({ ...entry, recordedAt: new Date().toISOString() });
  writeFileSync(file, JSON.stringify(entries, null, 2));
}

/** Picks the fixed E2E snapshot and a time with enough closed-candle history in UTC+7. */
async function prepareGemini(page: Page): Promise<void> {
  await page.goto("/replay");
  const select = page.getByTestId("replay-snapshot-select");
  await expect(select).toBeVisible();
  await expect(select.locator(`option[value="${SNAPSHOT_ID}"]`)).toHaveCount(1);
  await select.selectOption(SNAPSHOT_ID);
  await expect(page.getByTestId("replay-load-status")).toContainText(`#${SHORT_ID}`);

  await page.getByTestId("replay-time-input").fill(MID_WINDOW_INPUT);
  await expect(page.getByTestId("replay-load-status")).toContainText("2026-10-30");
  await page.getByTestId("replay-engine-gemini").click();
}

test.describe("gemini report", () => {
  test.setTimeout(120_000);

  test.beforeAll(() => {
    if (!SNAPSHOT_ID) throw new Error("Set E2E_SNAPSHOT_ID to an existing snapshot ID.");
  });

  test("dry-run report shows the simulated-data label and never calls Gemini", async ({ page }) => {
    await prepareGemini(page);

    const dryRun = page.getByTestId("replay-dry-run");
    await expect(dryRun).toBeChecked();
    await expect(page.getByText("Báo cáo sẽ mang nhãn DỮ LIỆU GIẢ LẬP")).toBeVisible();

    const [response] = await Promise.all([
      page.waitForResponse(
        (res) => res.url().includes("/api/external-analysis/jobs") && res.request().method() === "POST",
      ),
      page.getByTestId("replay-run-analysis").click(),
    ]);
    expect(response.status()).toBe(202);

    const job = (await response.json()) as { id: string; prediction_time_t_ms: number };
    recordJob({ kind: "gemini-mock", jobId: job.id, snapshotId: SNAPSHOT_ID, predictionTimeMs: String(job.prediction_time_t_ms) });

    await expect(page.getByTestId("replay-analysis")).toBeVisible();
    await expect(page.getByText("DỮ LIỆU GIẢ LẬP — chưa gọi Gemini.")).toBeVisible();
  });

  // Real Gemini call: costs Gemini quota. Excluded from the default run (grepInvert @real-gemini).
  // Run manually only with `npm run e2e:gemini`.
  test("@real-gemini creates one real Gemini report", async ({ page }) => {
    test.setTimeout(300_000);
    await prepareGemini(page);

    const dryRun = page.getByTestId("replay-dry-run");
    await dryRun.uncheck();
    await expect(dryRun).not.toBeChecked();

    const [response] = await Promise.all([
      page.waitForResponse(
        (res) => res.url().includes("/api/external-analysis/jobs") && res.request().method() === "POST",
      ),
      page.getByTestId("replay-run-analysis").click(),
    ]);
    expect(response.status()).toBe(202);

    const job = (await response.json()) as { id: string };
    recordJob({ kind: "gemini-real", jobId: job.id, snapshotId: SNAPSHOT_ID });

    await expect(page.getByTestId("replay-analysis")).toBeVisible();
    await expect(page.getByText("DỮ LIỆU GIẢ LẬP")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Nhận định hướng giá" })).toBeVisible({ timeout: 240_000 });
  });
});
