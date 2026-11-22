'use client';

import React, { useRef, useEffect, useState, useMemo, useCallback, useId } from 'react';
import { useRouter } from 'next/navigation';
import { CandleDTO } from './types';
import { Card, Badge, Notice } from '@/shared/ui/primitives';
import { formatDateTime, formatInt, formatUsd } from '@/shared/format';

interface SnapshotMeta {
  id: string;
  symbol: string;
  timeframe: string;
  start_time_ms: number;
  end_time_ms: number;
  candle_count: number;
}

interface CandlestickChartProps {
  initialCandles: CandleDTO[];
  timeframe: string;
  symbol: string;
  snapshotId: string;
  snapshotStartMs?: number;
  snapshotEndMs?: number;
  isPristine?: boolean;
  allSnapshots?: SnapshotMeta[];
}

const UTC7_MS = 7 * 3600 * 1000;
const CHART_HEIGHT = 460;
const PADDING_RIGHT = 75;

const COLOR = {
  grid: '#f0f0f0',
  axis: '#e0e0e0',
  label: '#6e6e73',
  crosshair: '#a1a1a6',
  up: '#1d8348',
  down: '#c0392b',
  upVolume: 'rgba(29, 131, 72, 0.28)',
  downVolume: 'rgba(192, 57, 43, 0.28)',
  gap: '#8a5a00',
};

const FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

export function CandlestickChart({
  initialCandles,
  timeframe,
  symbol,
  snapshotId,
  snapshotStartMs,
  snapshotEndMs,
  isPristine,
  allSnapshots,
}: CandlestickChartProps) {
  const router = useRouter();
  const uid = useId();
  const [candles, setCandles] = useState<CandleDTO[]>(initialCandles);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const defaultVisible = Math.min(candles.length, 120);
  const [visibleCount, setVisibleCount] = useState<number>(defaultVisible > 0 ? defaultVisible : 60);
  const [offsetRight, setOffsetRight] = useState<number>(0);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [showTable, setShowTable] = useState<boolean>(false);
  const [useUtc7, setUseUtc7] = useState<boolean>(true);
  const tzLabel = useUtc7 ? 'UTC+7' : 'UTC';
  // shared/format.ts always renders UTC+7; shifting back by 7h yields plain UTC.
  const showTime = useCallback(
    (ms: number) => formatDateTime(useUtc7 ? ms : ms - UTC7_MS),
    [useUtc7]
  );
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartXRef = useRef<number>(0);
  const dragStartOffsetRef = useRef<number>(0);
  // Date range inputs for jumping
  const [rangeStart, setRangeStart] = useState<string>('');
  const [rangeEnd, setRangeEnd] = useState<string>('');

  // Synchronize when initialCandles or snapshotId changes
  useEffect(() => {
    setCandles(initialCandles);
    setVisibleCount(Math.min(initialCandles.length, 120) || 60);
    setOffsetRight(0);
    setHoveredIndex(null);
    setMousePos(null);
  }, [initialCandles, snapshotId]);

  // Auto-populate date range picker from snapshot metadata
  useEffect(() => {
    if (snapshotStartMs !== undefined && snapshotEndMs !== undefined) {
      setRangeStart(showTime(snapshotStartMs).replace(' ', 'T'));
      setRangeEnd(showTime(snapshotEndMs).replace(' ', 'T'));
    }
  }, [snapshotStartMs, snapshotEndMs, showTime]);

  const intervalMs = timeframe === '5m' ? 5 * 60 * 1000 : 60 * 1000;

  const jumpToSnapshotStart = () => {
    if (snapshotStartMs !== undefined) {
      const endMs = snapshotEndMs !== undefined
        ? Math.min(snapshotEndMs, snapshotStartMs + 500 * intervalMs)
        : snapshotStartMs + 500 * intervalMs;
      fetchWindow(snapshotStartMs, endMs);
    }
  };

  const jumpToSnapshotEnd = () => {
    if (snapshotEndMs !== undefined) {
      const startMs = snapshotStartMs !== undefined
        ? Math.max(snapshotStartMs, snapshotEndMs - 500 * intervalMs)
        : snapshotEndMs - 500 * intervalMs;
      fetchWindow(startMs, snapshotEndMs);
    }
  };

  // Sliced candles based on pan/zoom
  const { visibleCandles, startIndex, endIndex } = useMemo(() => {
    if (candles.length === 0) {
      return { visibleCandles: [], startIndex: 0, endIndex: 0 };
    }
    const end = Math.max(0, candles.length - offsetRight);
    const start = Math.max(0, end - visibleCount);
    return {
      visibleCandles: candles.slice(start, end),
      startIndex: start,
      endIndex: end,
    };
  }, [candles, visibleCount, offsetRight]);

  // Detect gaps in visible window
  const gapCount = useMemo(() => {
    let count = 0;
    for (let i = 1; i < visibleCandles.length; i++) {
      const diff = visibleCandles[i].open_time_ms - visibleCandles[i - 1].close_time_ms;
      if (diff > 1000) {
        count++;
      }
    }
    return count;
  }, [visibleCandles]);

  // Fetch window from server API proxy
  const fetchWindow = async (startMs?: number, endMs?: number) => {
    setIsLoading(true);
    setFetchError(null);
    try {
      let clampedStart = startMs;
      let clampedEnd = endMs;
      if (snapshotStartMs !== undefined && clampedStart !== undefined) {
        clampedStart = Math.max(clampedStart, snapshotStartMs);
      }
      if (snapshotEndMs !== undefined && clampedEnd !== undefined) {
        clampedEnd = Math.min(clampedEnd, snapshotEndMs);
      }

      const params = new URLSearchParams();
      if (clampedStart !== undefined) params.set('start_ms', String(clampedStart));
      if (clampedEnd !== undefined) params.set('end_ms', String(clampedEnd));
      params.set('limit', '500');
      const res = await fetch(`/api/snapshots/${snapshotId}/candles?${params.toString()}`);
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || `HTTP ${res.status}`);
      }
      const data: CandleDTO[] = await res.json();
      if (data.length === 0) {
        setFetchError('Không tìm thấy nến trong khoảng yêu cầu.');
      } else {
        setCandles(data);
        setVisibleCount(Math.min(data.length, 120));
        setOffsetRight(0);
      }
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : 'Lỗi kết nối khi tải nến');
    } finally {
      setIsLoading(false);
    }
  };

  const applyRange = () => {
    const parseInputDate = (s: string): { val?: number; error?: string } => {
      const trimmed = s.trim();
      if (!trimmed) return {};
      let ms: number;
      const withSec = trimmed.length === 16 ? `${trimmed}:00` : trimmed;
      const hasExplicitTz = /(Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
      if (hasExplicitTz) {
        ms = Date.parse(trimmed);
      } else if (useUtc7) {
        ms = Date.parse(`${withSec}+07:00`);
      } else {
        ms = Date.parse(`${withSec}Z`);
      }
      if (isNaN(ms)) {
        return { error: `Định dạng thời gian không hợp lệ: "${s}".` };
      }
      return { val: ms };
    };

    let startMs: number | undefined = undefined;
    let endMs: number | undefined = undefined;
    if (rangeStart) {
      const res = parseInputDate(rangeStart);
      if (res.error) {
        setFetchError(res.error);
        return;
      }
      startMs = res.val;
    }
    if (rangeEnd) {
      const res = parseInputDate(rangeEnd);
      if (res.error) {
        setFetchError(res.error);
        return;
      }
      endMs = res.val;
    }
    if (startMs !== undefined && endMs !== undefined && startMs > endMs) {
      setFetchError('Thời gian bắt đầu phải nhỏ hơn hoặc bằng thời gian kết thúc.');
      return;
    }
    fetchWindow(startMs, endMs);
  };

  // Canvas drawing
  const renderChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    ctx.clearRect(0, 0, width, height);

    if (visibleCandles.length === 0) {
      ctx.fillStyle = COLOR.label;
      ctx.font = `14px ${FONT}`;
      ctx.textAlign = 'center';
      ctx.fillText('Không có dữ liệu nến trong khoảng được chọn', width / 2, height / 2);
      return;
    }

    const paddingBottom = 30;
    const chartHeight = height - paddingBottom;
    const mainChartHeight = chartHeight * 0.75;
    const volumeChartHeight = chartHeight * 0.22;
    const volumeTop = mainChartHeight + (chartHeight * 0.03);
    const plotWidth = width - PADDING_RIGHT;

    let minPrice = Infinity;
    let maxPrice = -Infinity;
    let maxVolume = 0;

    for (const c of visibleCandles) {
      if (c.low < minPrice) minPrice = c.low;
      if (c.high > maxPrice) maxPrice = c.high;
      if (c.volume > maxVolume) maxVolume = c.volume;
    }

    const priceRange = maxPrice - minPrice || 1;
    const paddedMin = minPrice - priceRange * 0.05;
    const paddedMax = maxPrice + priceRange * 0.05;
    const paddedRange = paddedMax - paddedMin;

    ctx.strokeStyle = COLOR.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = COLOR.label;
    ctx.font = `11px ${FONT}`;
    ctx.textAlign = 'left';

    // Horizontal price grid lines (5 levels)
    for (let i = 0; i <= 5; i++) {
      const price = paddedMin + (paddedRange / 5) * i;
      const y = mainChartHeight - ((price - paddedMin) / paddedRange) * mainChartHeight;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(plotWidth, y);
      ctx.stroke();
      ctx.fillText(`$${price.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`, plotWidth + 6, y + 4);
    }

    const candleSlotWidth = plotWidth / visibleCandles.length;
    const candleBodyWidth = Math.max(1, candleSlotWidth * 0.7);

    // Draw candles and volume bars
    for (let i = 0; i < visibleCandles.length; i++) {
      const c = visibleCandles[i];
      const isUp = c.close >= c.open;
      const color = isUp ? COLOR.up : COLOR.down;
      const x = i * candleSlotWidth + candleSlotWidth / 2;

      // Gap marker
      if (i > 0) {
        const gapMs = c.open_time_ms - visibleCandles[i - 1].close_time_ms;
        if (gapMs > 1000) {
          ctx.strokeStyle = COLOR.gap;
          ctx.lineWidth = 1;
          ctx.setLineDash([2, 4]);
          ctx.beginPath();
          ctx.moveTo(x - candleSlotWidth / 2, 0);
          ctx.lineTo(x - candleSlotWidth / 2, chartHeight);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      // High-low wick
      const wickHighY = mainChartHeight - ((c.high - paddedMin) / paddedRange) * mainChartHeight;
      const wickLowY = mainChartHeight - ((c.low - paddedMin) / paddedRange) * mainChartHeight;
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(1, candleSlotWidth * 0.12);
      ctx.beginPath();
      ctx.moveTo(x, wickHighY);
      ctx.lineTo(x, wickLowY);
      ctx.stroke();

      // Open-close body
      const openY = mainChartHeight - ((c.open - paddedMin) / paddedRange) * mainChartHeight;
      const closeY = mainChartHeight - ((c.close - paddedMin) / paddedRange) * mainChartHeight;
      const bodyTop = Math.min(openY, closeY);
      const bodyHeight = Math.max(1.5, Math.abs(closeY - openY));

      ctx.fillStyle = color;
      ctx.fillRect(x - candleBodyWidth / 2, bodyTop, candleBodyWidth, bodyHeight);

      // Volume bar
      const vH = maxVolume > 0 ? (c.volume / maxVolume) * volumeChartHeight : 0;
      ctx.fillStyle = isUp ? COLOR.upVolume : COLOR.downVolume;
      ctx.fillRect(x - candleBodyWidth / 2, chartHeight - vH, candleBodyWidth, vH);
    }

    // Baseline and time separator
    ctx.strokeStyle = COLOR.axis;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, chartHeight);
    ctx.lineTo(width, chartHeight);
    ctx.stroke();

    ctx.strokeStyle = COLOR.grid;
    ctx.beginPath();
    ctx.moveTo(0, volumeTop);
    ctx.lineTo(plotWidth, volumeTop);
    ctx.stroke();

    // Time labels (MM-DD HH:mm)
    ctx.fillStyle = COLOR.label;
    ctx.font = `11px ${FONT}`;
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(visibleCandles.length / 6));

    for (let i = 0; i < visibleCandles.length; i += step) {
      const c = visibleCandles[i];
      const x = i * candleSlotWidth + candleSlotWidth / 2;
      ctx.fillText(showTime(c.open_time_ms).slice(5), x, chartHeight + 16);
    }

    // Hover crosshair
    if (mousePos && hoveredIndex !== null && hoveredIndex >= 0 && hoveredIndex < visibleCandles.length) {
      const x = hoveredIndex * candleSlotWidth + candleSlotWidth / 2;
      const y = mousePos.y;

      ctx.strokeStyle = COLOR.crosshair;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, chartHeight);
      ctx.stroke();

      if (y <= mainChartHeight) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(plotWidth, y);
        ctx.stroke();
      }
      ctx.setLineDash([]);
    }
  }, [visibleCandles, mousePos, hoveredIndex, showTime]);

  const renderChartRef = useRef<() => void>(() => {});
  renderChartRef.current = renderChart;

  // Handle canvas resize cleanly with ResizeObserver (decoupled from renderChart)
  useEffect(() => {
    if (!containerRef.current) return;

    const applySize = (width: number) => {
      if (!canvasRef.current) return;
      const dpr = window.devicePixelRatio || 1;
      canvasRef.current.width = Math.round(width * dpr);
      canvasRef.current.height = Math.round(CHART_HEIGHT * dpr);
      canvasRef.current.style.width = `${width}px`;
      canvasRef.current.style.height = `${CHART_HEIGHT}px`;

      const ctx = canvasRef.current.getContext('2d');
      if (ctx) {
        ctx.resetTransform();
        ctx.scale(dpr, dpr);
      }
      renderChartRef.current();
    };

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        if (w > 0) {
          applySize(w);
        }
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    renderChart();
  }, [renderChart]);

  // Mouse wheel zoom on canvas (scroll up = zoom in, scroll down = zoom out)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      setVisibleCount((prev) => {
        if (e.deltaY < 0) {
          return Math.max(15, Math.round(prev * 0.85));
        } else {
          return Math.min(candles.length, Math.max(prev + 5, Math.round(prev * 1.15)));
        }
      });
    };
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', handleWheel);
  }, [candles.length]);

  // Window mouseup listener to cancel drag even when released outside canvas
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      setIsDragging(false);
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
  }, []);

  const hoveredCandle = hoveredIndex !== null ? visibleCandles[hoveredIndex] : null;
  const selectId = `${uid}-snapshot`;
  const rangeStartId = `${uid}-range-start`;
  const rangeEndId = `${uid}-range-end`;

  return (
    <Card>
      <div className="stack">
        <div className="spread">
          <div className="stack-sm">
            <div className="row">
              <h2 className="card-title">Biểu đồ nến</h2>
              <Badge variant="neutral">{symbol} {timeframe}</Badge>
              {isPristine === undefined ? (
                <Badge variant="neutral">Chưa có dữ liệu chất lượng</Badge>
              ) : (
                <Badge variant={isPristine ? 'success' : 'warning'}>
                  {isPristine ? 'Không thiếu khoảng' : 'Có khoảng thiếu'}
                </Badge>
              )}
            </div>
            <p className="card-sub">
              Nguồn: Binance Spot lịch sử, không phải giá trực tiếp. Múi giờ: {tzLabel}
              {useUtc7 ? ' (giờ Việt Nam)' : ''}.
            </p>
          </div>

          {allSnapshots && allSnapshots.length > 1 && (
            <div className="field">
              <label className="label" htmlFor={selectId}>Bộ dữ liệu</label>
              <select
                id={selectId}
                className="select data-chart-select"
                value={snapshotId}
                onChange={(e) => router.push(`/data?snapshot_id=${e.target.value}`)}
              >
                {allSnapshots.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.symbol} {s.timeframe} ({showTime(s.start_time_ms).slice(5, 10)} → {showTime(s.end_time_ms).slice(5, 10)}) · {formatInt(s.candle_count)} nến
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {fetchError && <Notice variant="error">{fetchError}</Notice>}

        <div className="chart-frame">
          {/* Viewport & navigation controls */}
          <div className="chart-toolbar">
            <div className="data-chart-group">
              {snapshotStartMs && (
                <button
                  type="button"
                  className="btn btn-quiet btn-sm"
                  onClick={jumpToSnapshotStart}
                  disabled={isLoading}
                >
                  Về đầu
                </button>
              )}
              {snapshotEndMs && (
                <button
                  type="button"
                  className="btn btn-quiet btn-sm"
                  onClick={jumpToSnapshotEnd}
                  disabled={isLoading}
                >
                  Tới cuối
                </button>
              )}
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                onClick={() => setOffsetRight((prev) => Math.min(candles.length - visibleCount, prev + Math.floor(visibleCount * 0.25)))}
                disabled={offsetRight >= candles.length - visibleCount}
              >
                Trượt trái
              </button>
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                onClick={() => setOffsetRight((prev) => Math.max(0, prev - Math.floor(visibleCount * 0.25)))}
                disabled={offsetRight <= 0}
              >
                Trượt phải
              </button>
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                onClick={() => setVisibleCount((prev) => Math.max(20, Math.floor(prev * 0.75)))}
                disabled={visibleCount <= 20}
              >
                Phóng to
              </button>
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                onClick={() => setVisibleCount((prev) => Math.min(candles.length, Math.floor(prev * 1.35)))}
                disabled={visibleCount >= candles.length}
              >
                Thu nhỏ
              </button>
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                onClick={() => {
                  setVisibleCount(Math.min(candles.length, 120));
                  setOffsetRight(0);
                }}
              >
                Đặt lại
              </button>
            </div>

            <div className="data-chart-group">
              <div className="seg" role="group" aria-label="Múi giờ hiển thị">
                <button type="button" className="seg-btn" aria-pressed={useUtc7} onClick={() => setUseUtc7(true)}>
                  UTC+7
                </button>
                <button type="button" className="seg-btn" aria-pressed={!useUtc7} onClick={() => setUseUtc7(false)}>
                  UTC
                </button>
              </div>
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                aria-pressed={showTable}
                onClick={() => setShowTable((v) => !v)}
              >
                {showTable ? 'Ẩn bảng số' : 'Hiện bảng số'}
              </button>
            </div>
          </div>

          {/* Date range jump */}
          <div className="chart-toolbar">
            <div className="data-chart-group">
              <label className="data-chart-field" htmlFor={rangeStartId}>
                Từ ({tzLabel})
                <input
                  id={rangeStartId}
                  type="datetime-local"
                  step="60"
                  className="input data-chart-input"
                  value={rangeStart}
                  onChange={(e) => setRangeStart(e.target.value)}
                />
              </label>
              <label className="data-chart-field" htmlFor={rangeEndId}>
                Đến ({tzLabel})
                <input
                  id={rangeEndId}
                  type="datetime-local"
                  step="60"
                  className="input data-chart-input"
                  value={rangeEnd}
                  onChange={(e) => setRangeEnd(e.target.value)}
                />
              </label>
              <button
                type="button"
                className="btn btn-sm"
                onClick={applyRange}
                disabled={isLoading || (!rangeStart && !rangeEnd)}
                title="Chuyển biểu đồ đến khoảng thời gian này trong bộ dữ liệu đang chọn"
              >
                {isLoading ? 'Đang tải...' : 'Xem khoảng này'}
              </button>
            </div>
            <span>Chỉ xem nến trong bộ dữ liệu đang chọn.</span>
          </div>

          {/* Hovered info strip */}
          <div className="data-chart-info">
            {hoveredCandle ? (
              <>
                <span>{showTime(hoveredCandle.open_time_ms)} ({tzLabel})</span>
                <span>Mở {formatUsd(hoveredCandle.open)}</span>
                <span>Cao {formatUsd(hoveredCandle.high)}</span>
                <span>Thấp {formatUsd(hoveredCandle.low)}</span>
                <span className={hoveredCandle.close >= hoveredCandle.open ? 'data-up' : 'data-down'}>
                  Đóng {formatUsd(hoveredCandle.close)}
                </span>
                <span>Khối lượng {hoveredCandle.volume.toFixed(4)} BTC</span>
                <span>Giao dịch {formatInt(hoveredCandle.trades_count)}</span>
              </>
            ) : (
              <span className="data-chart-info-idle">
                Kéo chuột để trượt, cuộn chuột để phóng to hoặc thu nhỏ. Đang hiển thị {formatInt(visibleCandles.length)} / {formatInt(candles.length)} nến
                {visibleCandles.length > 0 ? ` (${formatInt(startIndex + 1)} → ${formatInt(endIndex)})` : ''}.
                {gapCount > 0 && (
                  <span className="data-warn"> Có {gapCount} khoảng thiếu nến (vạch đứt).</span>
                )}
              </span>
            )}
          </div>

          {/* Canvas */}
          <div
            ref={containerRef}
            className={`data-chart-stage${isDragging ? ' is-dragging' : ''}`}
          >
            <canvas
              ref={canvasRef}
              className="chart-canvas"
              role="img"
              aria-label={`Biểu đồ nến ${symbol} ${timeframe}`}
              onMouseDown={(e) => {
                if (e.button === 0 && candles.length > visibleCount) {
                  setIsDragging(true);
                  dragStartXRef.current = e.clientX;
                  dragStartOffsetRef.current = offsetRight;
                }
              }}
              onMouseUp={() => setIsDragging(false)}
              onMouseMove={(e) => {
                const canvas = canvasRef.current;
                if (!canvas) return;
                const rect = canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const plotWidth = rect.width - PADDING_RIGHT;

                if (isDragging) {
                  const deltaX = e.clientX - dragStartXRef.current;
                  const slotWidth = plotWidth / Math.max(1, visibleCandles.length);
                  const candleShift = Math.round(deltaX / Math.max(1, slotWidth));
                  const newOffset = Math.max(
                    0,
                    Math.min(candles.length - visibleCount, dragStartOffsetRef.current + candleShift)
                  );
                  setOffsetRight(newOffset);
                  setHoveredIndex(null);
                  setMousePos(null);
                  return;
                }

                if (x >= 0 && x <= plotWidth && visibleCandles.length > 0) {
                  const slotWidth = plotWidth / visibleCandles.length;
                  const idx = Math.min(visibleCandles.length - 1, Math.max(0, Math.floor(x / slotWidth)));
                  setHoveredIndex(idx);
                  setMousePos({ x, y });
                } else {
                  setHoveredIndex(null);
                  setMousePos(null);
                }
              }}
              onMouseLeave={() => {
                if (!isDragging) {
                  setHoveredIndex(null);
                  setMousePos(null);
                }
              }}
              onTouchStart={(e) => {
                if (e.touches.length === 1 && candles.length > visibleCount) {
                  setIsDragging(true);
                  dragStartXRef.current = e.touches[0].clientX;
                  dragStartOffsetRef.current = offsetRight;
                }
              }}
              onTouchEnd={() => setIsDragging(false)}
              onTouchMove={(e) => {
                if (!isDragging || e.touches.length !== 1 || !canvasRef.current) return;
                const rect = canvasRef.current.getBoundingClientRect();
                const plotWidth = rect.width - PADDING_RIGHT;
                const deltaX = e.touches[0].clientX - dragStartXRef.current;
                const slotWidth = plotWidth / Math.max(1, visibleCandles.length);
                const candleShift = Math.round(deltaX / Math.max(1, slotWidth));
                const newOffset = Math.max(
                  0,
                  Math.min(candles.length - visibleCount, dragStartOffsetRef.current + candleShift)
                );
                setOffsetRight(newOffset);
              }}
            />
          </div>

          {/* Optional table */}
          {showTable && (
            <div className="data-chart-table">
              <table className="data-table">
                <caption className="visually-hidden">
                  Bảng nến trong vùng hiển thị ({visibleCandles.length} nến)
                </caption>
                <thead>
                  <tr>
                    <th>Thời gian ({tzLabel})</th>
                    <th>Giá mở</th>
                    <th>Giá cao</th>
                    <th>Giá thấp</th>
                    <th>Giá đóng</th>
                    <th>Khối lượng</th>
                    <th>Giao dịch</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleCandles.map((c) => (
                    <tr key={c.open_time_ms}>
                      <td>{showTime(c.open_time_ms)}</td>
                      <td>{formatUsd(c.open)}</td>
                      <td>{formatUsd(c.high)}</td>
                      <td>{formatUsd(c.low)}</td>
                      <td className={c.close >= c.open ? 'data-up' : 'data-down'}>{formatUsd(c.close)}</td>
                      <td>{c.volume.toFixed(4)}</td>
                      <td>{formatInt(c.trades_count)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
