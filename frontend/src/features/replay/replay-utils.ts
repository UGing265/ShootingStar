import type { CandleDTO } from '../data/types';
import type { StrategyEvaluationDTO } from './types';
import type { StrategyLevelsProps } from './replay-chart';

export const HORIZON_MINUTES = 30;
export const REQUIRED_HISTORY_HOURS = 6;
/** Candles fetched per replay window; the picked candle sits at WINDOW_PICK_RATIO of it. */
export const WINDOW_CANDLES = 1000;
export const WINDOW_PICK_RATIO = 0.75;

function timeframeMs(timeframe: string): number {
  const m = /^(\d+)([mh])$/.exec(timeframe);
  if (!m) return 60_000;
  return Number(m[1]) * (m[2] === 'h' ? 3_600_000 : 60_000);
}

/** `start_ms` for a candle window: ending at the snapshot end (`centerMs` null) or placing `centerMs` at 75% of it. */
export function windowStartMs(snapshot: { start_time_ms: number; end_time_ms: number; timeframe: string }, centerMs: number | null): number {
  const tf = timeframeMs(snapshot.timeframe);
  const raw = centerMs === null ? snapshot.end_time_ms - WINDOW_CANDLES * tf : centerMs - Math.floor(WINDOW_CANDLES * WINDOW_PICK_RATIO) * tf;
  return Math.max(snapshot.start_time_ms, raw);
}

const UTC7_OFFSET_MS = 7 * 3600 * 1000;

/** ms → value for `<input type="datetime-local">`, shown in UTC+7. */
export function toDateTimeLocal(ms: number): string {
  if (!ms || Number.isNaN(ms)) return '';
  return new Date(ms + UTC7_OFFSET_MS).toISOString().slice(0, 16);
}

/** `<input type="datetime-local">` value (read as UTC+7) → ms, or 0 when empty/invalid. */
export function fromDateTimeLocal(value: string): number {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value);
  if (!match) return 0;
  const [y, m, d, hh, mm] = match.slice(1).map(Number);
  return Date.UTC(y, m - 1, d, hh - 7, mm);
}

/** Default pick: candle at 75% of the loaded range, so ~6h of history precedes it. */
export function defaultPickIndex(length: number): number {
  return Math.min(length - 1, Math.max(0, Math.floor(length * 0.75)));
}

/** Hours of closed candles available before `buyTimeMs`. */
export function causalHours(candles: CandleDTO[], buyTimeMs: number): number {
  if (!buyTimeMs) return 0;
  const prior = candles.filter((c) => c.close_time_ms <= buyTimeMs);
  if (prior.length === 0) return 0;
  return (buyTimeMs - prior[0].open_time_ms) / 3_600_000;
}

export function strategyLevels(evaluation: StrategyEvaluationDTO | null | undefined): StrategyLevelsProps | null {
  if (!evaluation) return null;
  return {
    entryPrice: evaluation.proposed_entry,
    targetPrice: evaluation.target_price,
    stopPrice: evaluation.stop_price,
    zoneLow: evaluation.zone_low,
    zoneHigh: evaluation.zone_high,
  };
}
