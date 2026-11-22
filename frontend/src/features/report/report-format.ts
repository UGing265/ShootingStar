/**
 * Formatter for readable Vietnamese evidence analysis reports.
 * Adheres strictly to precision invariants:
 * - Up to 4-6 decimals for USDT/BTC to prevent nonzero underflow
 * - Strict heading deduplication (exact line match or `^[1-7]\.\s+`)
 * - Preserves sign and ratio precision
 */

import type { ForecastFeature } from '../replay/external-types';

export function formatUtc7Date(ms: number | string | null | undefined): string {
  if (!ms) return '';
  const num = typeof ms === 'string' ? parseInt(ms, 10) : ms;
  if (isNaN(num)) return String(ms);
  const d = new Date(num + 7 * 3600 * 1000);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  const sec = String(d.getUTCSeconds()).padStart(2, '0');
  return `${dd}/${mm}/${yyyy} ${hh}:${min}:${sec} (UTC+7)`;
}

export function formatPercentRatio(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return 'Chưa có dữ liệu';
  // Avoid negative zero
  if (Object.is(val, -0) || Math.abs(val) < 1e-9) return '0%';
  const pct = val * 100;
  const sign = pct > 0 ? '+' : '';
  // Keep up to 4 decimals of percentage (equivalent to 6 decimals ratio)
  const formatted = pct.toFixed(4).replace(/\.?0+$/, '');
  return `${sign}${formatted}%`;
}

export function formatUsdt(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return 'Chưa có dữ liệu';
  return `${val.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} USDT`;
}

export function formatBtc(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return 'Chưa có dữ liệu';
  // Preserve nonzero small quantities
  const maxDecimals = Math.abs(val) < 0.0001 && val !== 0 ? 6 : 4;
  return `${val.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: maxDecimals })} BTC`;
}

/**
 * Cleans section content safely:
 * 1. Strips duplicate heading ONLY if the first line is an exact match to sectionTitle
 *    or is a strict numbering prefix `^[1-7]\.\s+...`.
 * 2. Formats explicit epoch timestamp tokens like `178... ms`.
 * 3. Translates known debug variable parentheticals into Vietnamese.
 */
export function cleanSectionContent(rawContent: string, sectionTitle?: string): string {
  if (!rawContent) return '';
  let text = rawContent.trim();

  // 1. Strict heading deduplication
  const lines = text.split('\n');
  if (lines.length > 1) {
    const firstLine = lines[0].trim();
    const isExactTitle = sectionTitle && firstLine.toLowerCase() === sectionTitle.trim().toLowerCase();
    const isNumberedHeading = /^[1-7]\.\s+[\p{L}\s]+$/u.test(firstLine);
    if (isExactTitle || isNumberedHeading) {
      text = lines.slice(1).join('\n').trim();
    }
  }

  // 2. Safe timestamp ranges with explicit "ms" token
  text = text.replace(/(\b\d{13}\b)\s*ms\s*(đến|-)\s*(\b\d{13}\b)\s*ms/g, (_m, t1, sep, t2) => {
    return `${formatUtc7Date(parseInt(t1, 10))} ${sep} ${formatUtc7Date(parseInt(t2, 10))}`;
  });

  text = text.replace(/(\b\d{13}\b)\s*ms/g, (_m, t) => {
    return formatUtc7Date(parseInt(t, 10));
  });
  // 3. Clean raw code identifiers and candle IDs
  text = text.replace(/\(?candle_(\d{12,13})\)?/g, (_m, t) => {
    return `(nến tại ${formatUtc7Date(parseInt(t, 10))})`;
  });

  text = text.replace(/close\[-(\d+)\]\s*=\s*([0-9.]+)/gi, (_m, n, p) => {
    return `giá đóng cửa ${n} nến trước là ${formatUsdt(parseFloat(p))}`;
  });
  text = text.replace(/close\[-(\d+)\]/gi, (_m, n) => {
    return `nến thứ ${n} trước đó`;
  });

  // 4. Correct raw ratio with appended % (e.g. 0.001768% -> 0.1768%)
  text = text.replace(/\b0\.00(\d{2,6})%/g, (_m, digits) => {
    const val = parseFloat(`0.00${digits}`) * 100;
    return `${val.toFixed(4).replace(/\.?0+$/, '')}%`;
  });

  // 5. Clean scientific notation in prose when preceded by ratio/return context (e.g. lợi nhuận -5e-06 -> lợi nhuận -0.0005%)
  text = text.replace(
    /(lợi nhuận|lãi lỗ|độ lệch|thay đổi|biến động|tỷ lệ|return|yield|ratio)\s*([+-]?\d+(?:\.\d+)?e[+-]?\d+)/gi,
    (_m, prefix, val) => {
      const num = parseFloat(val);
      if (!isNaN(num)) {
        return `${prefix} ${formatPercentRatio(num)}`;
      }
      return `${prefix} ${val}`;
    }
  );

  // 6. Translate known debug variable parentheticals
  const replacements: Array<[RegExp, (match: string, val: string) => string]> = [
    [
      /\(latest_close_vs_p_pct\):\s*([+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?)/gi,
      (_m, v) => `(Chênh lệch đóng cửa so với giá P): ${formatPercentRatio(parseFloat(v))}`,
    ],
    [
      /\(volatility_6h_pct\):\s*([+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?)/gi,
      (_m, v) => `(Biến động giá 6h): ${formatPercentRatio(parseFloat(v))}`,
    ],
    [
      /\(return_1h\):\s*([+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?)/gi,
      (_m, v) => `(Biến động giá 1h gần nhất): ${formatPercentRatio(parseFloat(v))}`,
    ],
    [
      /\(range_high_6h\):\s*([+-]?\d+(?:\.\d+)?)/gi,
      (_m, v) => `(Giá cao nhất 6h): ${formatUsdt(parseFloat(v))}`,
    ],
    [
      /\(range_low_6h\):\s*([+-]?\d+(?:\.\d+)?)/gi,
      (_m, v) => `(Giá thấp nhất 6h): ${formatUsdt(parseFloat(v))}`,
    ],
    [
      /\(total_volume_6h\):\s*([+-]?\d+(?:\.\d+)?)/gi,
      (_m, v) => `(Tổng khối lượng 6h): ${formatBtc(parseFloat(v))}`,
    ],
    [
      /\(last_candle_body_ratio\):\s*([+-]?\d+(?:\.\d+)?)/gi,
      (_m, v) => `(Tỷ lệ thân nến): ${(parseFloat(v) * 100).toFixed(1)}%`,
    ],
    [
      /\(last_candle_upper_wick_ratio\):\s*([+-]?\d+(?:\.\d+)?)/gi,
      (_m, v) => `(Bóng trên): ${(parseFloat(v) * 100).toFixed(1)}%`,
    ],
    [
      /\(last_candle_lower_wick_ratio\):\s*([+-]?\d+(?:\.\d+)?)/gi,
      (_m, v) => `(Bóng dưới): ${(parseFloat(v) * 100).toFixed(1)}%`,
    ],
  ];

  for (const [pattern, replacer] of replacements) {
    text = text.replace(pattern, replacer);
  }
  return text;
}

export interface CanonicalMetricRow {
  label: string;
  valueStr: string;
  unitMeaning: string;
}

export function formatCanonicalFeatureTable(
  features: Array<{ feature_id: string; value: number }> | undefined
): CanonicalMetricRow[] {
  if (!features || !Array.isArray(features)) return [];
  const featMap = new Map<string, number>();
  for (const f of features) {
    if (f && f.feature_id) {
      featMap.set(f.feature_id, f.value);
    }
  }

  const rows: CanonicalMetricRow[] = [];

  if (featMap.has('latest_close_vs_p_pct')) {
    rows.push({
      label: 'Chênh lệch giá đóng cửa gần nhất so với giá tại thời điểm dự báo (P)',
      valueStr: formatPercentRatio(featMap.get('latest_close_vs_p_pct')),
      unitMeaning: 'Tỷ lệ % độ lệch giá',
    });
  }
  if (featMap.has('range_high_6h')) {
    rows.push({
      label: 'Phạm vi giá cao nhất trong 6 giờ',
      valueStr: formatUsdt(featMap.get('range_high_6h')),
      unitMeaning: 'Mức đỉnh 6h (USDT)',
    });
  }
  if (featMap.has('range_low_6h')) {
    rows.push({
      label: 'Phạm vi giá thấp nhất trong 6 giờ',
      valueStr: formatUsdt(featMap.get('range_low_6h')),
      unitMeaning: 'Mức đáy 6h (USDT)',
    });
  }
  if (featMap.has('volatility_6h_pct')) {
    rows.push({
      label: 'Biến động giá trong 6 giờ',
      valueStr: formatPercentRatio(featMap.get('volatility_6h_pct')),
      unitMeaning: 'Biên độ cao - thấp / giá thấp (%)',
    });
  }
  if (featMap.has('total_volume_6h')) {
    rows.push({
      label: 'Tổng khối lượng giao dịch trong 6 giờ',
      valueStr: formatBtc(featMap.get('total_volume_6h')),
      unitMeaning: 'Khối lượng cơ sở (BTC)',
    });
  }
  if (featMap.has('return_1h')) {
    rows.push({
      label: 'Biến động giá trong 1 giờ gần nhất',
      valueStr: formatPercentRatio(featMap.get('return_1h')),
      unitMeaning: 'Độ thay đổi giá 1h (%)',
    });
  }
  if (featMap.has('last_candle_body_ratio')) {
    rows.push({
      label: 'Tỷ lệ thân nến cuối cùng',
      valueStr: `${((featMap.get('last_candle_body_ratio') || 0) * 100).toFixed(1)}%`,
      unitMeaning: '% tổng biên độ nến',
    });
  }
  if (featMap.has('last_candle_upper_wick_ratio')) {
    rows.push({
      label: 'Tỷ lệ bóng trên nến cuối cùng',
      valueStr: `${((featMap.get('last_candle_upper_wick_ratio') || 0) * 100).toFixed(1)}%`,
      unitMeaning: '% tổng biên độ nến',
    });
  }
  if (featMap.has('last_candle_lower_wick_ratio')) {
    rows.push({
      label: 'Tỷ lệ bóng dưới nến cuối cùng',
      valueStr: `${((featMap.get('last_candle_lower_wick_ratio') || 0) * 100).toFixed(1)}%`,
      unitMeaning: '% tổng biên độ nến',
    });
  }

  return rows;
}

const FORECAST_FEATURE_NAMES: Record<string, string> = {
  ema20_slope: 'Độ dốc EMA20',
  ema50_slope: 'Độ dốc EMA50',
  rsi14: 'RSI 14',
  macd_hist: 'MACD histogram',
  atr14_pct: 'ATR 14',
  volume_ratio20: 'Tỷ lệ khối lượng 20 nến',
  swing_high_24h: 'Đỉnh 24 giờ',
  swing_low_24h: 'Đáy 24 giờ',
};

function forecastFeatureBaseName(name: string): string {
  const known = FORECAST_FEATURE_NAMES[name];
  if (known) return known;
  const range = /^range_position_(\d+)([hd])$/.exec(name);
  if (range) return `Vị trí giá trong biên ${range[1]} ${range[2] === 'd' ? 'ngày' : 'giờ'}`;
  const ret = /^return_(\d+)([hd])$/.exec(name);
  if (ret) return `Lợi nhuận ${ret[1]} ${ret[2] === 'd' ? 'ngày' : 'giờ'}`;
  return name.replace(/_/g, ' ');
}

/** Readable Vietnamese label for a forecast digest feature. */
export function forecastFeatureName(feature: ForecastFeature): string {
  return `${forecastFeatureBaseName(feature.name)} (${feature.timeframe})`;
}

/** Formats a digest value using the unit declared by the backend. */
export function formatForecastFeatureValue(feature: ForecastFeature): string {
  const value = feature.value;
  if (value === null || value === undefined || Number.isNaN(value)) return 'Chưa có dữ liệu';
  if (Math.abs(value) < 1e-9) return feature.unit === '%' ? '0%' : '0';
  if (feature.unit === 'price') return formatUsdt(value);
  if (feature.unit === '%') {
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toFixed(4).replace(/\.?0+$/, '')}%`;
  }
  if (feature.unit === 'index') return value.toFixed(2);
  if (feature.name.startsWith('volume_ratio')) return `${value.toFixed(2)} lần`;
  if (feature.name.startsWith('range_position')) return `${(value * 100).toFixed(1)}%`;
  return value.toFixed(4);
}

/** Replaces raw feature ids in model prose with readable labels. */
export function replaceForecastFeatureIds(text: string, features: ForecastFeature[]): string {
  let result = text;
  for (const feature of features) {
    if (!feature.feature_id) continue;
    result = result.split(feature.feature_id).join(forecastFeatureName(feature));
  }
  return result;
}

export interface ForecastCitation {
  label: string;
  value: string;
}

/** Turns cited feature ids into readable name/value pairs; never exposes the raw id. */
export function forecastCitations(featureIds: string[], features: ForecastFeature[]): ForecastCitation[] {
  const byId = new Map(features.map((feature) => [feature.feature_id, feature]));
  return featureIds.map((featureId) => {
    const feature = byId.get(featureId);
    if (!feature) return { label: 'Chỉ số không xác định', value: 'Chưa có dữ liệu' };
    return { label: forecastFeatureName(feature), value: formatForecastFeatureValue(feature) };
  });
}
