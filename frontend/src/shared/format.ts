/**
 * Display formatters shared across features.
 * All times shown to users are UTC+7 (project rule). Numbers use en-US so server
 * and browser render identical strings (no hydration mismatch).
 */

const UTC7_OFFSET_MS = 7 * 3600 * 1000;

function parts(ms: number) {
  const d = new Date(ms + UTC7_OFFSET_MS);
  const p = (n: number) => String(n).padStart(2, '0');
  return {
    yyyy: d.getUTCFullYear(),
    mm: p(d.getUTCMonth() + 1),
    dd: p(d.getUTCDate()),
    hh: p(d.getUTCHours()),
    min: p(d.getUTCMinutes()),
    ss: p(d.getUTCSeconds()),
  };
}

/** `2026-11-09 14:30` in UTC+7. */
export function formatDateTime(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return 'Chưa có dữ liệu';
  const t = parts(ms);
  return `${t.yyyy}-${t.mm}-${t.dd} ${t.hh}:${t.min}`;
}

/** `2026-11-09 14:30 (UTC+7)`. */
export function formatDateTimeTz(ms: number | null | undefined): string {
  const base = formatDateTime(ms);
  return base === 'Chưa có dữ liệu' ? base : `${base} (UTC+7)`;
}

/** `2026-11-09` in UTC+7. */
export function formatDate(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return 'Chưa có dữ liệu';
  const t = parts(ms);
  return `${t.yyyy}-${t.mm}-${t.dd}`;
}

/** `14:30` in UTC+7. */
export function formatTime(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return '';
  const t = parts(ms);
  return `${t.hh}:${t.min}`;
}

/** ISO timestamp string from the API (UTC) → `YYYY-MM-DD HH:mm` in UTC+7. */
export function formatIsoDateTime(iso: string | null | undefined): string {
  if (!iso) return 'Chưa có dữ liệu';
  const ms = Date.parse(iso.endsWith('Z') || /[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  return formatDateTime(ms);
}

/** `$67,123.45` */
export function formatUsd(value: number | null | undefined, maxDecimals = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'Chưa có dữ liệu';
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: maxDecimals })}`;
}

/** `1,234` */
export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'Chưa có dữ liệu';
  return value.toLocaleString('en-US');
}

/** Value is already a percentage (e.g. 0.12 → `+0.12%`). */
export function formatPct(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'Chưa có dữ liệu';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

export function directionLabel(direction: string | null | undefined): string {
  switch (direction) {
    case 'UP':
      return 'Tăng';
    case 'DOWN':
      return 'Giảm';
    case 'FLAT':
      return 'Đi ngang';
    case 'ABSTAIN':
      return 'Không dự báo';
    default:
      return 'Chưa có dữ liệu';
  }
}

export function directionArrow(direction: string | null | undefined): string {
  return direction === 'UP' ? '▲' : direction === 'DOWN' ? '▼' : direction === 'FLAT' ? '—' : '';
}
