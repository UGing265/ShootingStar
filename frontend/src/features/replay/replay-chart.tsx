'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { CandleDTO } from '../data/types';

export interface StrategyLevelsProps {
  entryPrice?: number | null;
  targetPrice?: number | null; // TP
  stopPrice?: number | null;   // SL
  zoneLow?: number | null;
  zoneHigh?: number | null;
}

export interface ReplayChartProps {
  candles: CandleDTO[];
  phase: 'selection' | 'analysis' | 'result';
  buyTimeMs: number;
  buyPrice: number;
  targetTimeMs?: number;
  targetPrice?: number | null;
  targetCandleCloseMs?: number | null;
  evidenceTimes?: number[];
  strategyLevels?: StrategyLevelsProps | null;
  onSelect?: (candle: CandleDTO) => void;
  showAll?: boolean;
  timeframe?: string;
  height?: number;
}

function formatUtc7(ms: number): string {
  if (!ms || isNaN(ms)) return 'N/A';
  const d = new Date(ms + 7 * 3600 * 1000);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd} ${hh}:${min} (UTC+7)`;
}

function formatTimeOnlyUtc7(ms: number): string {
  if (!ms || isNaN(ms)) return '';
  const d = new Date(ms + 7 * 3600 * 1000);
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  return `${hh}:${min}`;
}

export function ReplayChart({
  candles,
  phase,
  buyTimeMs,
  buyPrice,
  targetTimeMs,
  targetPrice = null,
  targetCandleCloseMs = null,
  evidenceTimes = [],
  strategyLevels = null,
  onSelect,
  showAll = false,
  timeframe = '1m',
  height = 360,
}: ReplayChartProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);


  // In analysis phase: strictly filter out any candle beyond buyTimeMs to prevent lookahead leakage
  const effectiveCandles = useMemo(() => {
    if (phase === 'analysis' && buyTimeMs > 0) {
      return candles.filter((c) => c.close_time_ms <= buyTimeMs);
    }
    return candles;
  }, [candles, phase, buyTimeMs]);

  // Windowing state
  const [visibleCount, setVisibleCount] = useState<number>(showAll ? Math.min(effectiveCandles.length, 180) : 100);
  const [offsetRight, setOffsetRight] = useState<number>(0);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartXRef = useRef<number>(0);
  const dragStartOffsetRef = useRef<number>(0);
  const hasDraggedRef = useRef<boolean>(false);

  // Re-sync visibleCount if candles array changes significantly
  useEffect(() => {
    if (effectiveCandles.length > 0 && visibleCount > effectiveCandles.length) {
      setVisibleCount(Math.min(effectiveCandles.length, 100));
    }
  }, [effectiveCandles.length]);

  const { visibleCandles, startIndex, endIndex } = useMemo(() => {
    if (effectiveCandles.length === 0) return { visibleCandles: [], startIndex: 0, endIndex: 0 };
    const end = Math.max(0, effectiveCandles.length - offsetRight);
    const start = Math.max(0, end - visibleCount);
    return {
      visibleCandles: effectiveCandles.slice(start, end),
      startIndex: start,
      endIndex: end,
    };
  }, [effectiveCandles, visibleCount, offsetRight]);

  // Wheel zoom handler
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      setVisibleCount((prev) => {
        if (e.deltaY < 0) {
          return Math.max(15, Math.round(prev * 0.82));
        } else {
          return Math.min(effectiveCandles.length + (phase === 'analysis' ? 35 : 0), Math.max(prev + 5, Math.round(prev * 1.22)));
        }
      });
    };

    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', handleWheel);
  }, [effectiveCandles.length, phase]);

  // Global mouse up
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      setIsDragging(false);
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
  }, []);

  // Main draw function
  const drawChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    if (visibleCandles.length === 0 && effectiveCandles.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '13px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Đang tải dữ liệu biểu đồ...', w / 2, h / 2);
      return;
    }

    const padL = 60;
    const padR = 50;
    const padT = 32;
    const padB = 40;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    // Determine price bounds
    let minP = visibleCandles.length > 0 ? Math.min(...visibleCandles.map((c) => c.low)) : (buyPrice || 100);
    let maxP = visibleCandles.length > 0 ? Math.max(...visibleCandles.map((c) => c.high)) : (buyPrice || 100);

    if (buyPrice > 0) {
      minP = Math.min(minP, buyPrice * 0.998);
      maxP = Math.max(maxP, buyPrice * 1.002);
    }
    if (targetPrice && targetPrice > 0) {
      minP = Math.min(minP, targetPrice * 0.998);
      maxP = Math.max(maxP, targetPrice * 1.002);
    }
    if (strategyLevels) {
      if (strategyLevels.targetPrice && strategyLevels.targetPrice > 0) {
        minP = Math.min(minP, strategyLevels.targetPrice * 0.998);
        maxP = Math.max(maxP, strategyLevels.targetPrice * 1.002);
      }
      if (strategyLevels.stopPrice && strategyLevels.stopPrice > 0) {
        minP = Math.min(minP, strategyLevels.stopPrice * 0.998);
        maxP = Math.max(maxP, strategyLevels.stopPrice * 1.002);
      }
      if (strategyLevels.entryPrice && strategyLevels.entryPrice > 0) {
        minP = Math.min(minP, strategyLevels.entryPrice * 0.998);
        maxP = Math.max(maxP, strategyLevels.entryPrice * 1.002);
      }
      if (strategyLevels.zoneLow && strategyLevels.zoneLow > 0) {
        minP = Math.min(minP, strategyLevels.zoneLow * 0.998);
      }
      if (strategyLevels.zoneHigh && strategyLevels.zoneHigh > 0) {
        maxP = Math.max(maxP, strategyLevels.zoneHigh * 1.002);
      }
    }

    const priceSpan = Math.max(maxP - minP, 1);

    // Determine dynamic horizon duration and slots
    const horizonMin = targetTimeMs && buyTimeMs ? Math.max(1, Math.round((targetTimeMs - buyTimeMs) / 60000)) : 30;
    const tfMs = visibleCandles.length > 1 ? Math.max(60000, visibleCandles[1].open_time_ms - visibleCandles[0].open_time_ms) : 60000;
    const horizonSlots = targetTimeMs && buyTimeMs ? Math.max(5, Math.round((targetTimeMs - buyTimeMs) / tfMs)) : 30;
    const extraSlots = phase === 'analysis' && targetTimeMs && buyTimeMs ? horizonSlots : 0;
    const totalSlots = Math.max(visibleCandles.length + extraSlots, 1);
    const stepX = plotW / totalSlots;
    const candleW = Math.max(2, stepX * 0.7);
    // 1. Draw horizontal grid lines & price ticks
    ctx.strokeStyle = '#f1f5f9';
    ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
      const y = padT + (plotH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(w - padR, y);
      ctx.stroke();

      const pVal = maxP - (priceSpan / 4) * i;
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(pVal.toFixed(1), padL - 8, y + 4);
    }

    // 2. In result phase: highlight the 30m evaluation window [buyTimeMs, targetTimeMs]
    let buyXCoord: number | null = null;
    let targetXCoord: number | null = null;

    // Match coordinates for buy and target
    visibleCandles.forEach((c, idx) => {
      const x = padL + idx * stepX + stepX / 2;
      if (Math.abs(c.close_time_ms - buyTimeMs) < 65000 || Math.abs(c.open_time_ms - buyTimeMs) < 65000) {
        buyXCoord = x;
      }
      if (targetCandleCloseMs && Math.abs(c.close_time_ms - targetCandleCloseMs) < 65000) {
        targetXCoord = x;
      } else if (targetTimeMs && !targetXCoord && Math.abs(c.close_time_ms - targetTimeMs) < 65000) {
        targetXCoord = x;
      }
    });

    if (phase === 'result' && buyXCoord !== null) {
      const rightBoundX = targetXCoord !== null ? targetXCoord : Math.min(w - padR, buyXCoord + stepX * horizonSlots);
      const spanW = Math.max(10, rightBoundX - buyXCoord);
      // Shaded interval band
      ctx.fillStyle = 'rgba(37, 99, 235, 0.07)';
      ctx.fillRect(buyXCoord, padT, spanW, plotH);

      // Boundary vertical lines
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#93c5fd';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(buyXCoord, padT);
      ctx.lineTo(buyXCoord, padT + plotH);
      ctx.moveTo(rightBoundX, padT);
      ctx.lineTo(rightBoundX, padT + plotH);
      ctx.stroke();
      ctx.restore();

      // Interval header
      ctx.fillStyle = '#2563eb';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`Khoảng dự đoán (${horizonMin} phút)`, buyXCoord + spanW / 2, padT - 8);
    }

    // 3. Render candles
    let selectedMarkerX: number | null = null;
    let selectedMarkerY: number | null = null;

    visibleCandles.forEach((c, idx) => {
      const x = padL + idx * stepX + stepX / 2;
      const isUp = c.close >= c.open;
      const col = isUp ? '#16a34a' : '#dc2626';

      const highY = padT + ((maxP - c.high) / priceSpan) * plotH;
      const lowY = padT + ((maxP - c.low) / priceSpan) * plotH;
      const openY = padT + ((maxP - c.open) / priceSpan) * plotH;
      const closeY = padT + ((maxP - c.close) / priceSpan) * plotH;

      // Check evidence highlight
      const isEvidence = evidenceTimes.some((et) => Math.abs(c.close_time_ms - et) < 60000 || Math.abs(c.open_time_ms - et) < 60000);
      if (isEvidence) {
        ctx.fillStyle = 'rgba(234, 179, 8, 0.2)';
        ctx.fillRect(x - stepX / 2, padT, stepX, plotH);
      }

      // Wick
      ctx.strokeStyle = col;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, highY);
      ctx.lineTo(x, lowY);
      ctx.stroke();

      // Body
      const bodyTop = Math.min(openY, closeY);
      const bodyH = Math.max(Math.abs(closeY - openY), 1.5);
      ctx.fillStyle = col;
      ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH);

      // Selected buy candle check
      if (Math.abs(c.close_time_ms - buyTimeMs) < 65000 || Math.abs(c.open_time_ms - buyTimeMs) < 65000) {
        selectedMarkerX = x;
        selectedMarkerY = closeY;
      }
    });

    // 4. In analysis phase: render masked future region on the right
    if (phase === 'analysis') {
      const maskStartX = padL + visibleCandles.length * stepX;
      const maskW = (w - padR) - maskStartX;

      if (maskW > 5) {
        // Draw diagonal hatched or clean frosted area
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(maskStartX, padT, maskW, plotH);

        // Dashed border at mask start
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = '#cbd5e1';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(maskStartX, padT);
        ctx.lineTo(maskStartX, padT + plotH);
        ctx.stroke();
        ctx.restore();

        // Shaded diagonal stripes
        ctx.save();
        ctx.beginPath();
        ctx.rect(maskStartX, padT, maskW, plotH);
        ctx.clip();
        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 1;
        for (let stripe = maskStartX - plotH; stripe < maskStartX + maskW + plotH; stripe += 16) {
          ctx.beginPath();
          ctx.moveTo(stripe, padT);
          ctx.lineTo(stripe + plotH, padT + plotH);
          ctx.stroke();
        }
        ctx.restore();

        // Overlay Badge
        const badgeW = 200;
        const badgeH = 46;
        const badgeX = maskStartX + (maskW - badgeW) / 2;
        const badgeY = padT + (plotH - badgeH) / 2;

        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = '#cbd5e1';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 6);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#475569';
        ctx.font = 'bold 11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`🔒 Vùng dự đoán (+${horizonMin}m)`, badgeX + badgeW / 2, badgeY + 18);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px sans-serif';
        ctx.fillText('Chưa mở — không nhìn trước', badgeX + badgeW / 2, badgeY + 34);

        // Right tick time at target horizon
        if (targetTimeMs) {
          ctx.fillStyle = '#64748b';
          ctx.font = '10px monospace';
          ctx.textAlign = 'center';
          ctx.fillText(`+${horizonMin}m (${formatTimeOnlyUtc7(targetTimeMs)})`, w - padR - 10, h - 12);
        }
      }
    }

    // 5. Time labels at bottom
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    const labelStep = Math.max(1, Math.floor(visibleCandles.length / 5));
    for (let i = 0; i < visibleCandles.length; i += labelStep) {
      const c = visibleCandles[i];
      const x = padL + i * stepX + stepX / 2;
      ctx.fillText(formatTimeOnlyUtc7(c.close_time_ms), x, h - 12);
    }

    // UTC+7 indicator
    ctx.fillStyle = '#64748b';
    ctx.font = 'bold 9px monospace';
    ctx.textAlign = 'right';
    ctx.fillText('UTC+7', w - padR + 36, h - 12);

    // 6. Horizontal Buy Price Line
    if (buyPrice > 0) {
      const lineY = padT + ((maxP - buyPrice) / priceSpan) * plotH;
      ctx.save();
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(padL, lineY);
      ctx.lineTo(w - padR, lineY);
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle = '#2563eb';
      ctx.font = 'bold 11px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(`Điểm mua P: $${buyPrice.toLocaleString()}`, padL + 8, lineY - 6);
    }

    // 7. Dot Marker on Chart for Buy Point
    const buyMarkerX = selectedMarkerX !== null ? selectedMarkerX : (phase === 'analysis' && offsetRight === 0 ? padL + visibleCandles.length * stepX - stepX / 2 : null);
    if (buyMarkerX !== null && buyPrice > 0) {
      const targetMarkerY = padT + ((maxP - buyPrice) / priceSpan) * plotH;

      ctx.beginPath();
      ctx.arc(buyMarkerX, targetMarkerY, 8, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(37, 99, 235, 0.25)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(buyMarkerX, targetMarkerY, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#2563eb';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // 8. Result marker in result phase
    if (phase === 'result' && targetPrice !== null && targetPrice > 0) {
      const resultY = padT + ((maxP - targetPrice) / priceSpan) * plotH;
      const resultX = targetXCoord !== null ? targetXCoord : (buyXCoord !== null ? buyXCoord + stepX * 30 : w - padR - 20);
      const isProfitable = targetPrice > buyPrice;
      const isLoss = targetPrice < buyPrice;
      const markerColor = isProfitable ? '#16a34a' : isLoss ? '#dc2626' : '#d97706';

      // Horizontal dashed line for target price
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = markerColor;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(padL, resultY);
      ctx.lineTo(w - padR, resultY);
      ctx.stroke();
      ctx.restore();

      // Dot marker
      ctx.beginPath();
      ctx.arc(resultX, resultY, 9, 0, Math.PI * 2);
      ctx.fillStyle = isProfitable ? 'rgba(22, 163, 74, 0.25)' : isLoss ? 'rgba(220, 38, 38, 0.25)' : 'rgba(217, 119, 6, 0.25)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(resultX, resultY, 5, 0, Math.PI * 2);
      ctx.fillStyle = markerColor;
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = markerColor;
      ctx.font = 'bold 11px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(`Kết quả: $${targetPrice.toLocaleString()} (${isProfitable ? '▲ UP' : isLoss ? '▼ DOWN' : 'FLAT'})`, w - padR - 8, resultY - 6);
    }

    // 9. Strategy Barrier Overlays (Vùng mua, Chốt lời TP, Cắt lỗ SL)
    if (strategyLevels) {
      // 9a. Entry Zone Band
      if (strategyLevels.zoneLow && strategyLevels.zoneHigh && strategyLevels.zoneHigh > strategyLevels.zoneLow) {
        const zoneTopY = padT + ((maxP - strategyLevels.zoneHigh) / priceSpan) * plotH;
        const zoneBottomY = padT + ((maxP - strategyLevels.zoneLow) / priceSpan) * plotH;
        ctx.fillStyle = 'rgba(2, 132, 199, 0.08)';
        ctx.fillRect(padL, zoneTopY, plotW, zoneBottomY - zoneTopY);
      }

      // 9b. Proposed Entry Line
      if (strategyLevels.entryPrice && strategyLevels.entryPrice > 0) {
        const entryY = padT + ((maxP - strategyLevels.entryPrice) / priceSpan) * plotH;
        ctx.save();
        ctx.setLineDash([4, 3]);
        ctx.strokeStyle = '#0284c7';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(padL, entryY);
        ctx.lineTo(w - padR, entryY);
        ctx.stroke();
        ctx.restore();

        ctx.fillStyle = '#0284c7';
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`Vùng mua đề xuất: $${strategyLevels.entryPrice.toLocaleString()}`, padL + 8, entryY - 4);
      }

      // 9c. Take Profit (TP) Line
      if (strategyLevels.targetPrice && strategyLevels.targetPrice > 0) {
        const tpY = padT + ((maxP - strategyLevels.targetPrice) / priceSpan) * plotH;
        ctx.save();
        ctx.setLineDash([6, 3]);
        ctx.strokeStyle = '#16a34a';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(padL, tpY);
        ctx.lineTo(w - padR, tpY);
        ctx.stroke();
        ctx.restore();

        ctx.fillStyle = '#16a34a';
        ctx.font = 'bold 11px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`Chốt lời (TP): $${strategyLevels.targetPrice.toLocaleString()}`, padL + 8, tpY - 5);
      }

      // 9d. Stop Loss (SL) Line
      if (strategyLevels.stopPrice && strategyLevels.stopPrice > 0) {
        const slY = padT + ((maxP - strategyLevels.stopPrice) / priceSpan) * plotH;
        ctx.save();
        ctx.setLineDash([6, 3]);
        ctx.strokeStyle = '#dc2626';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(padL, slY);
        ctx.lineTo(w - padR, slY);
        ctx.stroke();
        ctx.restore();

        ctx.fillStyle = '#dc2626';
        ctx.font = 'bold 11px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`Cắt lỗ (SL): $${strategyLevels.stopPrice.toLocaleString()}`, padL + 8, slY + 12);
      }
    }
  }, [visibleCandles, effectiveCandles.length, buyPrice, buyTimeMs, targetTimeMs, targetPrice, targetCandleCloseMs, evidenceTimes, strategyLevels, phase]);

  useEffect(() => {
    drawChart();
  }, [drawChart]);

  // Mouse pan and click selection
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (e.button === 0) {
      setIsDragging(true);
      hasDraggedRef.current = false;
      dragStartXRef.current = e.clientX;
      dragStartOffsetRef.current = offsetRight;
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDragging) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const deltaX = e.clientX - dragStartXRef.current;
    if (Math.abs(deltaX) > 3) {
      hasDraggedRef.current = true;
    }
    const rect = canvas.getBoundingClientRect();
    const scaleX = rect.width > 0 ? canvas.width / rect.width : 1;
    const padL = 60;
    const padR = 50;
    const plotW = canvas.width - padL - padR;
    const slotWidth = plotW / Math.max(1, visibleCandles.length);
    const candleShift = Math.round((deltaX * scaleX) / Math.max(1, slotWidth));
    const maxOffset = Math.max(0, effectiveCandles.length - visibleCount);
    const newOffset = Math.max(0, Math.min(maxOffset, dragStartOffsetRef.current + candleShift));
    setOffsetRight(newOffset);
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(false);
    if (!hasDraggedRef.current && phase === 'selection' && onSelect) {
      const canvas = canvasRef.current;
      if (!canvas || visibleCandles.length === 0) return;
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const padL = 60;
      const padR = 50;
      const plotW = canvas.width - padL - padR;
      const relX = (x / rect.width) * canvas.width - padL;
      if (relX < 0 || relX > plotW) return;
      const slotWidth = plotW / Math.max(1, visibleCandles.length);
      const clickedIdx = Math.floor(relX / slotWidth);
      if (clickedIdx >= 0 && clickedIdx < visibleCandles.length) {
        onSelect(visibleCandles[clickedIdx]);
      }
    }
  };

  return (
    <div
      style={{
        position: 'relative',
        background: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: 6,
        overflow: 'hidden',
      }}
    >
      {/* Chart Toolbar */}
      <div
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          zIndex: 10,
          display: 'flex',
          gap: 6,
          background: 'rgba(255, 255, 255, 0.92)',
          padding: '4px 6px',
          borderRadius: 4,
          border: '1px solid #e2e8f0',
        }}
      >
        <button
          type="button"
          onClick={() => setVisibleCount((prev) => Math.max(15, Math.round(prev * 0.75)))}
          title="Phóng to (Zoom In)"
          style={{ padding: '3px 8px', fontSize: 12, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 4, cursor: 'pointer' }}
        >
          +
        </button>
        <button
          type="button"
          onClick={() => setVisibleCount((prev) => Math.min(effectiveCandles.length + 30, Math.round(prev * 1.35)))}
          title="Thu nhỏ (Zoom Out)"
          style={{ padding: '3px 8px', fontSize: 12, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 4, cursor: 'pointer' }}
        >
          −
        </button>
        <button
          type="button"
          onClick={() => {
            setVisibleCount(Math.min(effectiveCandles.length, 100) || 60);
            setOffsetRight(0);
          }}
          title="Đặt lại khung nhìn"
          style={{ padding: '3px 8px', fontSize: 11, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 4, cursor: 'pointer' }}
        >
          ⟲ Đặt lại
        </button>
      </div>

      <canvas
        ref={canvasRef}
        width={960}
        height={height}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        style={{
          width: '100%',
          height: `${height}px`,
          cursor: isDragging ? 'grabbing' : phase === 'selection' ? 'crosshair' : 'default',
          display: 'block',
          userSelect: 'none',
        }}
      />
    </div>
  );
}
