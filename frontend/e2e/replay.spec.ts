import { test, expect, type Locator, type Page } from "@playwright/test";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

// Next 16 blocks its dev resources for the 127.0.0.1 host, so client bundles never hydrate there;
// localhost reaches the same server on port 3100 and keeps the checks against the real hydrated app.
test.use({ baseURL: "http://localhost:3100" });

const SNAPSHOT_ID = process.env.E2E_SNAPSHOT_ID ?? "";
const SHORT_ID = SNAPSHOT_ID.slice(0, 8);

/** Snapshot window used by the tests: half-way through the stored 30 days, in UTC+7. */
const MID_WINDOW_INPUT = "2026-10-30T12:00";
const OUTSIDE_INPUT = "2026-12-01T12:00";
/** Bất kỳ mốc hợp lệ nào dùng để xoá lỗi trước khi kiểm tra lại lỗi biên. */
const CLEARING_INPUT = "2026-11-20T12:00";

function recordJob(entry: Record<string, string>): void {
  const file = path.resolve(process.cwd(), "e2e", ".created-jobs.json");
  const existing: unknown = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : [];
  const entries = Array.isArray(existing) ? (existing as Record<string, string>[]) : [];
  entries.push({ ...entry, recordedAt: new Date().toISOString() });
  writeFileSync(file, JSON.stringify(entries, null, 2));
}

interface SnapshotSelection {
  select: Locator;
  status: Locator;
  /** Option label: `SYMBOL · TF · N nến · START → END · #SHORT_ID`. */
  label: string;
  /** Snapshot end as `YYYY-MM-DD HH:mm` in UTC+7. */
  end: string;
}

async function openReplaySnapshot(page: Page): Promise<SnapshotSelection> {
  await page.goto("/replay");
  const select = page.getByTestId("replay-snapshot-select");
  await expect(select).toBeVisible();

  const option = select.locator(`option[value="${SNAPSHOT_ID}"]`);
  await expect(option).toHaveCount(1);
  const label = (await option.textContent()) ?? "";
  const end = (label.split("→")[1] ?? "").split("·")[0].trim();

  await select.selectOption(SNAPSHOT_ID);
  const status = page.getByTestId("replay-load-status");
  await expect(status).toContainText(`#${SHORT_ID}`);

  return { select, status, label, end };
}

/** `YYYY-MM-DD HH:mm` (UTC+7) shifted by whole minutes, formatted the same way. */
function shiftUtc7(label: string, minutes: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/.exec(label);
  if (!match) throw new Error(`Snapshot end label is not a date time: "${label}"`);
  const [y, mo, d, hh, mm] = match.slice(1).map(Number);
  return new Date(Date.UTC(y, mo - 1, d, hh, mm) + minutes * 60_000).toISOString().slice(0, 16);
}

test.describe("replay", () => {
  test.setTimeout(120_000);

  test.beforeAll(() => {
    if (!SNAPSHOT_ID) throw new Error("Set E2E_SNAPSHOT_ID to an existing snapshot ID.");
  });

  test("dropdown option carries the snapshot date range and short id", async ({ page }) => {
    const { label } = await openReplaySnapshot(page);

    expect(label).toMatch(/#[0-9a-f]{8}$/);
    expect(label).toContain(`#${SHORT_ID}`);
    expect(label).toMatch(/\d{4}-\d{2}-\d{2} \d{2}:\d{2} → \d{4}-\d{2}-\d{2} \d{2}:\d{2}/);
  });

  test("default window ends at the snapshot end", async ({ page }) => {
    const { status, end } = await openReplaySnapshot(page);

    expect(end).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
    await expect(status).toContainText("nến đang tải");
    await expect(status).toContainText(`→ ${end}`);
  });

  test("a time inside the window loads candles and changes the price", async ({ page }) => {
    const { status } = await openReplaySnapshot(page);
    const price = page.getByTestId("replay-price-input");
    await expect(price).not.toHaveValue("");
    const priceBefore = await price.inputValue();

    await page.getByTestId("replay-time-input").fill(MID_WINDOW_INPUT);

    await expect(status).toContainText("2026-10-30");
    await expect(price).not.toHaveValue(priceBefore);
    await expect(page.getByTestId("replay-time-error")).toHaveCount(0);
  });

  test("a time outside the snapshot is rejected and the price is kept", async ({ page }) => {
    await openReplaySnapshot(page);
    const price = page.getByTestId("replay-price-input");
    await expect(price).not.toHaveValue("");
    const priceBefore = await price.inputValue();

    await page.getByTestId("replay-time-input").fill(OUTSIDE_INPUT);

    await expect(page.getByTestId("replay-time-error")).toContainText("Ngoài phạm vi snapshot");
    await expect(price).toHaveValue(priceBefore);
  });

  test("a time inside the last 30 minutes is rejected like out of range", async ({ page }) => {
    const { end } = await openReplaySnapshot(page);
    const time = page.getByTestId("replay-time-input");
    const price = page.getByTestId("replay-price-input");
    const error = page.getByTestId("replay-time-error");

    // Clear any previous error with a valid time first.
    await time.fill(CLEARING_INPUT);
    await expect(error).toHaveCount(0);

    const edgeInput = shiftUtc7(end, -10);
    const priceBefore = await price.inputValue();
    await time.fill(edgeInput);

    await expect(error).toContainText("Ngoài phạm vi snapshot");
    await expect(price).toHaveValue(priceBefore);
  });

  test("strategy dry-run returns an entry-zone result or a clear state", async ({ page }) => {
    const { status } = await openReplaySnapshot(page);
    await page.getByTestId("replay-time-input").fill(MID_WINDOW_INPUT);
    await expect(status).toContainText("2026-10-30");
    await page.getByTestId("replay-engine-strategy").click();

    const [response] = await Promise.all([
      page.waitForResponse((res) => res.url().includes("/api/replay/jobs") && res.request().method() === "POST"),
      page.getByTestId("replay-run-analysis").click(),
    ]);
    expect(response.status()).toBe(201);

    const job = (await response.json()) as { job_id: string; buy_time_ms: number };
    recordJob({ kind: "strategy", jobId: job.job_id, snapshotId: SNAPSHOT_ID, buyTimeMs: String(job.buy_time_ms) });

    await expect(page.getByTestId("replay-analysis")).toBeVisible();
    await expect(
      page.getByTestId("replay-strategy-title").or(page.getByText("Chưa có vùng vào lệnh.")),
    ).toBeVisible();
  });
});
