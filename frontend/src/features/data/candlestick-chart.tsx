'use client';

import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { CandleDTO } from './types';
import { Card, Badge } from '@/shared/ui/primitives';

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
  const tzOffsetMs = useUtc7 ? 7 * 3600 * 1000 : 0;
  const tzLabel = useUtc7 ? 'UTC+7' : 'UTC';
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartXRef = useRef<number>(0);
  const dragStartOffsetRef = useRef<number>(0);
  // Date range inputs for jumping
  const [rangeStart, setRangeStart] = useState<string>('');
  const [rangeEnd, setRangeEnd] = useState<string>('');

  // Synchronize when initialCandles changes
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
      const formatLocalIso = (ms: number) => {
        const d = new Date(ms + tzOffsetMs);
        return d.toISOString().slice(0, 16);
      };
      setRangeStart(formatLocalIso(snapshotStartMs));
      setRangeEnd(formatLocalIso(snapshotEndMs));
    }
  }, [snapshotStartMs, snapshotEndMs, tzOffsetMs]);

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
      ctx.fillStyle = '#7a7a7a';
      ctx.font = '14px -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Không có dữ liệu nến trong khoảng được chọn', width / 2, height / 2);
      return;
    }

    const paddingRight = 75;
    const paddingBottom = 30;
    const chartHeight = height - paddingBottom;
    const mainChartHeight = chartHeight * 0.75;
    const volumeChartHeight = chartHeight * 0.22;
    const volumeTop = mainChartHeight + (chartHeight * 0.03);
    const plotWidth = width - paddingRight;

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

    ctx.strokeStyle = '#f0f0f2';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#7a7a7a';
    ctx.font = '11px -apple-system, ui-monospace, monospace';
    ctx.textAlign = 'left';

    // Horizontal price grid lines (5 levels)
    for (let i = 0; i <= 5; i++) {
      const price = paddedMin + (paddedRange / 5) * i;
      const y = mainChartHeight - ((price - paddedMin) / paddedRange) * mainChartHeight;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(plotWidth, y);
      ctx.stroke();
      ctx.fillText(`$${price.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`, plotWidth + 6, y + 4);
    }

    const candleSlotWidth = plotWidth / visibleCandles.length;
    const candleBodyWidth = Math.max(1, candleSlotWidth * 0.7);

    // Draw candles and volume bars
    for (let i = 0; i < visibleCandles.length; i++) {
      const c = visibleCandles[i];
      const isUp = c.close >= c.open;
      const color = isUp ? '#34c759' : '#ff3b30';
      const x = i * candleSlotWidth + candleSlotWidth / 2;

      // Gap marker
      if (i > 0) {
        const gapMs = c.open_time_ms - visibleCandles[i - 1].close_time_ms;
        if (gapMs > 1000) {
          ctx.strokeStyle = '#ff9500';
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
      ctx.fillStyle = isUp ? 'rgba(52, 199, 89, 0.4)' : 'rgba(255, 59, 48, 0.4)';
      ctx.fillRect(x - candleBodyWidth / 2, chartHeight - vH, candleBodyWidth, vH);
    }

    // Baseline and time separator
    ctx.strokeStyle = '#e5e5ea';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, chartHeight);
    ctx.lineTo(width, chartHeight);
    ctx.stroke();

    ctx.strokeStyle = '#f0f0f2';
    ctx.beginPath();
    ctx.moveTo(0, volumeTop);
    ctx.lineTo(plotWidth, volumeTop);
    ctx.stroke();

    // Time labels
    ctx.fillStyle = '#7a7a7a';
    ctx.font = '11px -apple-system, monospace';
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(visibleCandles.length / 6));

    for (let i = 0; i < visibleCandles.length; i += step) {
      const c = visibleCandles[i];
      const x = i * candleSlotWidth + candleSlotWidth / 2;
      const d = new Date(c.open_time_ms + tzOffsetMs);
      ctx.fillText(`${d.toISOString().slice(5, 10)} ${d.toISOString().slice(11, 16)}`, x, chartHeight + 16);
    }

    // Hover crosshair
    if (mousePos && hoveredIndex !== null && hoveredIndex >= 0 && hoveredIndex < visibleCandles.length) {
      const x = hoveredIndex * candleSlotWidth + candleSlotWidth / 2;
      const y = mousePos.y;

      ctx.strokeStyle = '#a1a1a6';
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
  }, [visibleCandles, mousePos, hoveredIndex, tzOffsetMs]);

  const renderChartRef = useRef<() => void>(() => {});
  renderChartRef.current = renderChart;

  // Handle canvas resize cleanly with ResizeObserver (decoupled from renderChart)
  useEffect(() => {
    if (!containerRef.current) return;

    const applySize = (width: number) => {
      if (!canvasRef.current) return;
      const dpr = window.devicePixelRatio || 1;
      const height = 460;
      canvasRef.current.width = Math.round(width * dpr);
      canvasRef.current.height = Math.round(height * dpr);
      canvasRef.current.style.width = `${width}px`;
      canvasRef.current.style.height = `${height}px`;

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

  return (
    <Card>
      {/* Header and Provenance Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <h2 style={{ fontSize: 20, fontWeight: 600 }}>Biểu đồ nến Lịch sử giá (OHLCV)</h2>
            <Badge variant="neutral">{symbol} {timeframe}</Badge>
            <Badge variant={isPristine ? 'success' : 'warning'}>
              {isPristine ? 'Không thiếu khoảng' : 'Có khoảng trống (gap)'}
            </Badge>
          </div>
          <p style={{ fontSize: 13, color: 'var(--ink-muted)', marginTop: 4 }}>
            Múi giờ: <strong>{tzLabel}</strong> {useUtc7 ? '(Giờ Việt Nam)' : ''} | Horizon dự đoán: <strong>30m</strong> (tách biệt) | 
            Nguồn: Binance Spot lịch sử (không phải giá live)
          </p>
          {allSnapshots && allSnapshots.length > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
              <span style={{ fontSize: 13, color: 'var(--ink-muted)', fontWeight: 500 }}>📂 Chọn bản snapshot:</span>
              <select
                value={snapshotId}
                onChange={(e) => router.push(`/data?snapshot_id=${e.target.value}`)}
                style={{
                  padding: '6px 10px',
                  border: '1px solid var(--hairline)',
                  borderRadius: 6,
                  fontSize: 13,
                  background: '#fff',
                  color: 'var(--ink)',
                  cursor: 'pointer',
                }}
              >
                {allSnapshots.map((s) => {
                  const sStart = new Date(s.start_time_ms + tzOffsetMs).toISOString().slice(5, 10);
                  const sEnd = new Date(s.end_time_ms + tzOffsetMs).toISOString().slice(5, 10);
                  return (
                    <option key={s.id} value={s.id}>
                      {s.symbol} {s.timeframe} ({sStart} → {sEnd}) • {s.candle_count.toLocaleString()} nến
                    </option>
                  );
                })}
              </select>
            </div>
          )}
        </div>

        {/* Viewport & Navigation Controls */}
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
          {snapshotStartMs && (
            <button
              type="button"
              onClick={jumpToSnapshotStart}
              disabled={isLoading}
              className="button"
              style={{ padding: '6px 12px', fontSize: 13 }}
            >
              ⏮ Đầu snapshot
            </button>
          )}
          {snapshotEndMs && (
            <button
              type="button"
              onClick={jumpToSnapshotEnd}
              disabled={isLoading}
              className="button"
              style={{ padding: '6px 12px', fontSize: 13 }}
            >
              ⏭ Cuối snapshot
            </button>
          )}
          <button
            type="button"
            onClick={() => setOffsetRight((prev) => Math.min(candles.length - visibleCount, prev + Math.floor(visibleCount * 0.25)))}
            disabled={offsetRight >= candles.length - visibleCount}
            className="button"
            style={{ padding: '6px 12px', fontSize: 13 }}
          >
            Trượt trái
          </button>
          <button
            type="button"
            onClick={() => setOffsetRight((prev) => Math.max(0, prev - Math.floor(visibleCount * 0.25)))}
            disabled={offsetRight <= 0}
            className="button"
            style={{ padding: '6px 12px', fontSize: 13 }}
          >
            Trượt phải
          </button>
          <button
            type="button"
            onClick={() => setVisibleCount((prev) => Math.max(20, Math.floor(prev * 0.75)))}
            disabled={visibleCount <= 20}
            className="button"
            style={{ padding: '6px 12px', fontSize: 13 }}
          >
            Thu phóng +
          </button>
          <button
            type="button"
            onClick={() => setVisibleCount((prev) => Math.min(candles.length, Math.floor(prev * 1.35)))}
            disabled={visibleCount >= candles.length}
            className="button"
            style={{ padding: '6px 12px', fontSize: 13 }}
          >
            Thu nhỏ -
          </button>
          <button
            type="button"
            onClick={() => {
              setVisibleCount(Math.min(candles.length, 120));
              setOffsetRight(0);
            }}
            className="button"
            style={{ padding: '6px 12px', fontSize: 13 }}
          >
            Đặt lại
          </button>
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            className="button"
            style={{ padding: '6px 12px', fontSize: 13, background: showTable ? 'var(--surface-pearl)' : undefined }}
          >
            {showTable ? 'Ẩn bảng số' : 'Hiện bảng số'}
          </button>
          <button
            type="button"
            onClick={() => setUseUtc7((v) => !v)}
            className="button"
            style={{ padding: '6px 12px', fontSize: 13, background: useUtc7 ? 'var(--surface-pearl)' : undefined }}
          >
            {useUtc7 ? '🕒 Múi giờ: UTC+7 (Đổi sang UTC)' : '🕒 Múi giờ: UTC (Đổi sang UTC+7)'}
          </button>
        </div>
      </div>

      {/* Date Range Jump Controls */}
      {/* Date Range Jump Controls with native Calendar Picker */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 12, fontSize: 13 }}>
        <span style={{ color: 'var(--ink-muted)', fontWeight: 500 }}>📅 Khung nhìn biểu đồ ({tzLabel}):</span>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ color: 'var(--ink-muted)', fontSize: 12 }}>Từ:</span>
          <input
            type="datetime-local"
            step="60"
            value={rangeStart}
            onChange={(e) => setRangeStart(e.target.value)}
            style={{
              padding: '5px 10px',
              border: '1px solid var(--hairline)',
              borderRadius: 6,
              fontSize: 13,
              background: '#fff',
              color: 'var(--ink)',
            }}
          />
        </label>
        <span>→</span>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ color: 'var(--ink-muted)', fontSize: 12 }}>Đến:</span>
          <input
            type="datetime-local"
            step="60"
            value={rangeEnd}
            onChange={(e) => setRangeEnd(e.target.value)}
            style={{
              padding: '5px 10px',
              border: '1px solid var(--hairline)',
              borderRadius: 6,
              fontSize: 13,
              background: '#fff',
              color: 'var(--ink)',
            }}
          />
        </label>
        <button
          type="button"
          onClick={() => {
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
          }}
          disabled={isLoading || (!rangeStart && !rangeEnd)}
          className="button"
          style={{ padding: '5px 14px', fontSize: 13, fontWeight: 500 }}
          title="Di chuyển biểu đồ đến khoảng thời gian này trong snapshot đã chọn"
        >
          {isLoading ? 'Đang chuyển...' : 'Xem khoảng nến này'}
        </button>
        <span style={{ color: 'var(--ink-muted)', fontSize: 12 }}>(Chỉ xem nến trong snapshot đang chọn)</span>
        {fetchError && <span style={{ color: '#ff3b30', fontSize: 12 }}>{fetchError}</span>}
      </div>

      {/* Hovered Info Strip */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
          fontSize: 13,
          padding: '8px 12px',
          background: 'var(--surface-pearl)',
          borderRadius: 8,
          marginBottom: 12,
          fontFamily: 'var(--font-mono)',
        }}
      >
        {hoveredCandle ? (
          <>
            <span><strong>Thời gian:</strong> {new Date(hoveredCandle.open_time_ms + tzOffsetMs).toISOString().slice(0, 19).replace('T', ' ')} ({tzLabel})</span>
            <span><strong>Mở:</strong> ${hoveredCandle.open.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            <span><strong>Cao:</strong> ${hoveredCandle.high.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            <span><strong>Thấp:</strong> ${hoveredCandle.low.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
            <span>
              <strong>Đóng:</strong>{' '}
              <span style={{ color: hoveredCandle.close >= hoveredCandle.open ? '#34c759' : '#ff3b30', fontWeight: 600 }}>
                ${hoveredCandle.close.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
            </span>
            <span><strong>Khối lượng:</strong> {hoveredCandle.volume.toFixed(4)} BTC</span>
            <span><strong>Giao dịch:</strong> {hoveredCandle.trades_count}</span>
          </>
        ) : (
          <span style={{ color: 'var(--ink-muted)' }}>
            💡 <strong>Kéo giữ chuột trái</strong> để trượt nến qua lại | <strong>Cuộn chuột</strong> để phóng to / thu nhỏ. Hiển thị {visibleCandles.length} / {candles.length} nến ({startIndex + 1} → {endIndex}).
            {gapCount > 0 && <span style={{ color: '#ff9500', marginLeft: 8 }}>⚠️ Có {gapCount} khoảng thiếu nến (vạch đứt cam).</span>}
          </span>
        )}
      </div>

      {/* Canvas */}
      {/* Canvas */}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: 460,
          position: 'relative',
          cursor: isDragging ? 'grabbing' : 'crosshair',
          userSelect: 'none',
        }}
      >
        <canvas
          ref={canvasRef}
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
            const plotWidth = rect.width - 75;

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
            const plotWidth = rect.width - 75;
            const deltaX = e.touches[0].clientX - dragStartXRef.current;
            const slotWidth = plotWidth / Math.max(1, visibleCandles.length);
            const candleShift = Math.round(deltaX / Math.max(1, slotWidth));
            const newOffset = Math.max(
              0,
              Math.min(candles.length - visibleCount, dragStartOffsetRef.current + candleShift)
            );
            setOffsetRight(newOffset);
          }}
          style={{ width: '100%', height: '100%', display: 'block', touchAction: 'none' }}
        />
      </div>

      {/* Optional Table */}
      {showTable && (
        <div style={{ marginTop: 24, borderTop: '1px solid var(--hairline)', paddingTop: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
            Bảng nến trong vùng hiển thị ({visibleCandles.length} nến)
          </h3>
          <div className="table-responsive" style={{ maxHeight: 320, overflowY: 'auto' }}>
            <table className="data-table">
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
                    <td>{new Date(c.open_time_ms + tzOffsetMs).toISOString().slice(0, 19).replace('T', ' ')}</td>
                    <td>${c.open.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                    <td>${c.high.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                    <td>${c.low.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                    <td style={{ color: c.close >= c.open ? '#34c759' : '#ff3b30', fontWeight: 500 }}>
                      ${c.close.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td>{c.volume.toFixed(4)}</td>
                    <td>{c.trades_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  );
}
