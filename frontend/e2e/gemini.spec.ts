import { test, expect, type Page } from "@playwright/test";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

// Next 16 blocks its dev resources for the 127.0.0.1 host, so client bundles never hydrate there;
// localhost reaches the same server on port 3100 and keeps the checks against the real hydrated app.
test.use({ baseURL: "http://localhost:3100" });

const FORECAST_JOB_ID =
  process.env.E2E_FORECAST_JOB_ID ?? "1dfa822c-94d2-4287-8e71-4f58fac5332a";
const LEGACY_JOB_ID =
  process.env.E2E_LEGACY_JOB_ID ?? "484391ba-2182-415d-8afc-4519b4469e64";
const SNAPSHOT_ID = process.env.E2E_SNAPSHOT_ID ?? "";
const SHORT_ID = SNAPSHOT_ID.slice(0, 8);
const FORECAST_TIME_INPUT = process.env.E2E_FORECAST_TIME ?? "2026-10-30T12:00";

function recordJob(entry: Record<string, string>): void {
  const file = path.resolve(process.cwd(), "e2e", ".created-jobs.json");
  const existing: unknown = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : [];
  const entries = Array.isArray(existing) ? (existing as Record<string, string>[]) : [];
  entries.push({ ...entry, recordedAt: new Date().toISOString() });
  writeFileSync(file, JSON.stringify(entries, null, 2));
}

test.describe("saved forecast reports", () => {
  test("forecast-6h-v1 report renders direction, confidence, agreement and verification warning", async ({
    page,
  }) => {
    await page.goto(`/report?job=${encodeURIComponent(FORECAST_JOB_ID)}`);

    await expect(page.getByRole("heading", { name: "Nhận định hướng giá" })).toBeVisible();
    await expect(page.locator(".report-pill", { hasText: "GIẢM" })).toBeVisible();
    await expect(
      page.locator(".report-meta-value").filter({ hasText: /^Trung bình$/ }).first(),
    ).toBeVisible();
    await expect(page.getByText("model tự đánh giá, chưa kiểm chứng")).toBeVisible();
    await expect(page.getByText(/chỉ số cùng chiều/)).toBeVisible();

    await expect(page.getByText("Cảnh báo kiểm chứng.", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "So sánh với luật đơn giản" })).toBeVisible();
    await expect(page.getByText("Luôn TĂNG", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Theo đà 6h", { exact: true }).first()).toBeVisible();

    await expect(page.getByRole("heading", { name: "Bảng điểm dự báo" })).toBeVisible();
    await expect(page.getByText(/Tổng \d+ mốc/)).toBeVisible();

    // Raw feature ids and raw job ids must never be the visible label.
    await expect(page.getByText("1h_ema20_slope")).toHaveCount(0);
    await expect(page.getByText(FORECAST_JOB_ID)).toHaveCount(0);
  });

  test("legacy 30-minute ABSTAIN job still renders", async ({ page }) => {
    await page.goto(`/report?job=${encodeURIComponent(LEGACY_JOB_ID)}`);

    await expect(page.getByRole("heading", { name: "Nhận định hướng giá" })).toBeVisible();
    await expect(page.getByText("Không dự báo").first()).toBeVisible();
    await expect(page.getByText("Không đủ căn cứ để dự báo").first()).toBeVisible();
  });
});

test.describe("real Gemini forecast", () => {
  // Real Gemini call: costs quota and writes a job to the main DB.
  // Excluded from the default run (grepInvert @real-gemini). Run manually with `npm run e2e:gemini`.
  test("@real-gemini creates one real 6-hour forecast report", async ({ page }) => {
    test.skip(!SNAPSHOT_ID, "Set E2E_SNAPSHOT_ID to create a real forecast job.");
    test.setTimeout(300_000);

    await page.goto("/replay");
    const select = page.getByTestId("replay-snapshot-select");
    await expect(select).toBeVisible();
    await expect(select.locator(`option[value="${SNAPSHOT_ID}"]`)).toHaveCount(1);
    await select.selectOption(SNAPSHOT_ID);
    await expect(page.getByTestId("replay-load-status")).toContainText(`#${SHORT_ID}`);

    await page.getByTestId("replay-time-input").fill(FORECAST_TIME_INPUT);
    await page.getByTestId("replay-engine-gemini").click();

    const [response] = await Promise.all([
      page.waitForResponse(
        (res) =>
          res.url().includes("/api/external-analysis/jobs") && res.request().method() === "POST",
      ),
      page.getByTestId("replay-run-analysis").click(),
    ]);
    expect(response.status()).toBe(202);

    const job = (await response.json()) as { id: string };
    recordJob({ kind: "gemini-real", jobId: job.id, snapshotId: SNAPSHOT_ID });

    await expect(page.getByTestId("replay-analysis")).toBeVisible();
    await expect(page.getByText("DỮ LIỆU GIẢ LẬP")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Nhận định hướng giá" })).toBeVisible({
      timeout: 280_000,
    });
  });
});
