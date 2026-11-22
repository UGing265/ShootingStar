/**
 * Browser-side list of reports the user generated, so the Báo cáo page can list them.
 * The backend has no "list jobs" endpoint; only job ids this browser created are shown.
 */

export interface RecentReport {
  id: string;
  symbol: string;
  timeframe: string;
  predictionTimeMs: number;
  purchasePrice: number;
  savedAtMs: number;
  /** True when the report was produced from simulated data, not a real Gemini call. */
  mock?: boolean;
}

/** Link to the report page. `mock=1` makes the page show the simulated-data label (the API does not report it). */
export function reportHref(id: string, mock: boolean): string {
  return `/report?job=${encodeURIComponent(id)}${mock ? '&mock=1' : ''}`;
}

const STORAGE_KEY = 'shootingstar.recent-reports';
const MAX_ENTRIES = 30;

export function loadRecentReports(): RecentReport[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as RecentReport[]) : [];
  } catch {
    return [];
  }
}

export function saveRecentReport(entry: RecentReport): void {
  try {
    const rest = loadRecentReports().filter((r) => r.id !== entry.id);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([entry, ...rest].slice(0, MAX_ENTRIES)));
  } catch {
    // Storage unavailable (private mode / quota): the report is still reachable by its link.
  }
}
