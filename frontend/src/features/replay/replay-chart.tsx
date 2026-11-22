'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { CandleDTO } from '../data/types';
import { formatDateTime, formatTime } from '../../shared/format';
import './replay-chart.css';

export interface StrategyLevelsProps {
  entryPrice?: number | null;
  targetPrice?: number | null; // TP
  stopPrice?: number | null;   // SL
  zoneLow?: number | null;
  zoneHigh?: number | null;
}

/** Canvas padding in drawing px. The right gutter holds the price labels. Shared by drawing and hit-testing. */
const PAD = { l: 60, r: 104, t: 40, b: 40 } as const;

interface GutterLabel {
  y: number;
  text: string;
  color: string;
  drawY: number;
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

  // Bring the chosen point into view: centered while selecting, buy→target near the right edge in the result.
  useEffect(() => {
    if (phase === 'analysis' || buyTimeMs <= 0 || effectiveCandles.length === 0) return;
    const focusMs = phase === 'result' && targetTimeMs ? targetTimeMs : buyTimeMs;
    const idx = effectiveCandles.findIndex((c) => c.close_time_ms >= focusMs);
    if (idx < 0) return;
    if (phase === 'selection' && idx >= startIndex && idx < endIndex) return;
    const maxOffset = Math.max(0, effectiveCandles.length - visibleCount);
    const keepRight = phase === 'result' ? Math.round(visibleCount * 0.12) : Math.round(visibleCount / 2);
    const offset = effectiveCandles.length - (idx + keepRight);
    setOffsetRight(Math.min(maxOffset, Math.max(0, offset)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, buyTimeMs, targetTimeMs, effectiveCandles]);

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
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, w, h);

    if (visibleCandles.length === 0 && effectiveCandles.length === 0) {
      ctx.fillStyle = '#6e6e73';
      ctx.font = '13px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Đang tải dữ liệu biểu đồ...', w / 2, h / 2);
      return;
    }

    const { l: padL, r: padR, t: padT, b: padB } = PAD;
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
    ctx.strokeStyle = '#f0f0f0';
    ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
      const y = padT + (plotH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(w - padR, y);
      ctx.stroke();

      const pVal = maxP - (priceSpan / 4) * i;
      ctx.fillStyle = '#6e6e73';
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
      ctx.fillStyle = 'rgba(0, 102, 204, 0.08)';
      ctx.fillRect(buyXCoord, padT, spanW, plotH);

      // Boundary vertical lines
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#7ab4e8';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(buyXCoord, padT);
      ctx.lineTo(buyXCoord, padT + plotH);
      ctx.moveTo(rightBoundX, padT);
      ctx.lineTo(rightBoundX, padT + plotH);
      ctx.stroke();
      ctx.restore();

      // Interval header
      ctx.fillStyle = '#0066cc';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`Khoảng dự đoán (${horizonMin} phút)`, buyXCoord + spanW / 2, padT - 6);
    }

    // 3. Render candles
    let selectedMarkerX: number | null = null;
    let selectedMarkerY: number | null = null;

    visibleCandles.forEach((c, idx) => {
      const x = padL + idx * stepX + stepX / 2;
      const isUp = c.close >= c.open;
      const col = isUp ? '#1d8348' : '#c0392b';

      const highY = padT + ((maxP - c.high) / priceSpan) * plotH;
      const lowY = padT + ((maxP - c.low) / priceSpan) * plotH;
      const openY = padT + ((maxP - c.open) / priceSpan) * plotH;
      const closeY = padT + ((maxP - c.close) / priceSpan) * plotH;

      // Check evidence highlight
      const isEvidence = evidenceTimes.some((et) => Math.abs(c.close_time_ms - et) < 60000 || Math.abs(c.open_time_ms - et) < 60000);
      if (isEvidence) {
        ctx.fillStyle = 'rgba(138, 90, 0, 0.14)';
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
        ctx.fillStyle = '#fafafc';
        ctx.fillRect(maskStartX, padT, maskW, plotH);

        // Dashed border at mask start
        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = '#d2d2d7';
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
        ctx.strokeStyle = '#e8e8ed';
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
        ctx.strokeStyle = '#e0e0e0';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 6);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#1d1d1f';
        ctx.font = '600 11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Vùng tương lai được ẩn', badgeX + badgeW / 2, badgeY + 18);
        ctx.fillStyle = '#6e6e73';
        ctx.font = '10px sans-serif';
        ctx.fillText(`Chưa mở · ${horizonMin} phút tới`, badgeX + badgeW / 2, badgeY + 34);

        // Right tick time at target horizon
        if (targetTimeMs) {
          ctx.fillStyle = '#6e6e73';
          ctx.font = '10px monospace';
          ctx.textAlign = 'center';
          ctx.fillText(`+${horizonMin}p (${formatTime(targetTimeMs)})`, w - padR - 10, h - 12);
        }
      }
    }

    // 5. Time labels at bottom
    ctx.fillStyle = '#6e6e73';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    const labelStep = Math.max(1, Math.floor(visibleCandles.length / 5));
    for (let i = 0; i < visibleCandles.length; i += labelStep) {
      const c = visibleCandles[i];
      const x = padL + i * stepX + stepX / 2;
      ctx.fillText(formatDateTime(c.close_time_ms).slice(5), x, h - 12);
    }

    // UTC+7 indicator
    ctx.fillStyle = '#6e6e73';
    ctx.font = 'bold 9px monospace';
    ctx.textAlign = 'right';
    ctx.fillText('UTC+7', w - 8, h - 12);

    // 6. Price lines. Labels sit in the right gutter, stacked so they never overlap candles or each other.
    const yOf = (p: number) => padT + ((maxP - p) / priceSpan) * plotH;
    const fmtPrice = (p: number) => p.toLocaleString('en-US', { maximumFractionDigits: p >= 1000 ? 0 : 2 });
    const gutterLabels: GutterLabel[] = [];
    const drawLine = (price: number, color: string, dash: number[], width: number) => {
      const y = yOf(price);
      ctx.save();
      ctx.setLineDash(dash);
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(w - padR, y);
      ctx.stroke();
      ctx.restore();
    };

    // Entry zone band
    if (strategyLevels?.zoneLow && strategyLevels.zoneHigh && strategyLevels.zoneHigh > strategyLevels.zoneLow) {
      const zoneTopY = yOf(strategyLevels.zoneHigh);
      const zoneBottomY = yOf(strategyLevels.zoneLow);
      ctx.fillStyle = 'rgba(0, 102, 204, 0.10)';
      ctx.fillRect(padL, zoneTopY, plotW, zoneBottomY - zoneTopY);
      drawLine(strategyLevels.zoneHigh, 'rgba(0, 102, 204, 0.35)', [], 1);
      drawLine(strategyLevels.zoneLow, 'rgba(0, 102, 204, 0.35)', [], 1);
    }

    if (buyPrice > 0) {
      drawLine(buyPrice, '#6e6e73', [2, 4], 1);
      gutterLabels.push({ y: yOf(buyPrice), text: `Giá ${fmtPrice(buyPrice)}`, color: '#6e6e73', drawY: 0 });
    }
    if (strategyLevels?.entryPrice && strategyLevels.entryPrice > 0) {
      drawLine(strategyLevels.entryPrice, '#0066cc', [4, 3], 1.5);
      gutterLabels.push({ y: yOf(strategyLevels.entryPrice), text: `Vào lệnh ${fmtPrice(strategyLevels.entryPrice)}`, color: '#0066cc', drawY: 0 });
    }
    if (strategyLevels?.targetPrice && strategyLevels.targetPrice > 0) {
      drawLine(strategyLevels.targetPrice, '#1d8348', [6, 3], 1.5);
      gutterLabels.push({ y: yOf(strategyLevels.targetPrice), text: `Chốt lời ${fmtPrice(strategyLevels.targetPrice)}`, color: '#1d8348', drawY: 0 });
    }
    if (strategyLevels?.stopPrice && strategyLevels.stopPrice > 0) {
      drawLine(strategyLevels.stopPrice, '#c0392b', [6, 3], 1.5);
      gutterLabels.push({ y: yOf(strategyLevels.stopPrice), text: `Cắt lỗ ${fmtPrice(strategyLevels.stopPrice)}`, color: '#c0392b', drawY: 0 });
    }

    // 7. Marker for the forecast moment: dot on the price line, dotted vertical line and a small tag above the plot.
    const buyMarkerX = selectedMarkerX !== null ? selectedMarkerX : (phase === 'analysis' && offsetRight === 0 ? padL + visibleCandles.length * stepX - stepX / 2 : null);
    if (buyMarkerX !== null && buyPrice > 0) {
      ctx.save();
      ctx.setLineDash([2, 3]);
      ctx.strokeStyle = '#0066cc';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(buyMarkerX, padT);
      ctx.lineTo(buyMarkerX, padT + plotH);
      ctx.stroke();
      ctx.restore();

      const markerY = yOf(buyPrice);
      ctx.beginPath();
      ctx.arc(buyMarkerX, markerY, 8, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 102, 204, 0.2)';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(buyMarkerX, markerY, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#0066cc';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.font = '600 10px sans-serif';
      const tagText = 'Thời điểm dự báo';
      const tagW = ctx.measureText(tagText).width + 12;
      const tagX = Math.max(padL, Math.min(buyMarkerX - tagW / 2, w - padR - tagW));
      ctx.fillStyle = '#e8f1fb';
      ctx.strokeStyle = '#0066cc';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(tagX, 6, tagW, 16, 8);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#0066cc';
      ctx.textAlign = 'left';
      ctx.fillText(tagText, tagX + 6, 17);
    }

    // 8. Result marker in result phase
    if (phase === 'result' && targetPrice !== null && targetPrice > 0) {
      const resultY = yOf(targetPrice);
      const resultX = targetXCoord !== null ? targetXCoord : (buyXCoord !== null ? buyXCoord + stepX * 30 : w - padR - 20);
      const isProfitable = targetPrice > buyPrice;
      const isLoss = targetPrice < buyPrice;
      const markerColor = isProfitable ? '#1d8348' : isLoss ? '#c0392b' : '#8a5a00';

      drawLine(targetPrice, markerColor, [4, 4], 1.5);

      ctx.beginPath();
      ctx.arc(resultX, resultY, 9, 0, Math.PI * 2);
      ctx.fillStyle = isProfitable ? 'rgba(29, 131, 72, 0.2)' : isLoss ? 'rgba(192, 57, 43, 0.2)' : 'rgba(138, 90, 0, 0.2)';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(resultX, resultY, 5, 0, Math.PI * 2);
      ctx.fillStyle = markerColor;
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      gutterLabels.push({ y: resultY, text: `Kết quả ${fmtPrice(targetPrice)}`, color: markerColor, drawY: 0 });
    }

    // 9. Stack gutter labels top-to-bottom with a minimum gap, then pull them back up if they overflow the bottom.
    const labelGap = 18;
    const labelTop = padT + 9;
    const labelBottom = padT + plotH - 9;
    const stacked = [...gutterLabels].sort((a, b) => a.y - b.y);
    stacked.forEach((label, i) => {
      label.drawY = Math.max(Math.min(label.y, labelBottom), i > 0 ? stacked[i - 1].drawY + labelGap : labelTop);
    });
    for (let i = stacked.length - 1; i >= 0; i--) {
      const limit = i === stacked.length - 1 ? labelBottom : stacked[i + 1].drawY - labelGap;
      if (stacked[i].drawY > limit) stacked[i].drawY = limit;
    }
    ctx.font = 'bold 10px sans-serif';
    ctx.textAlign = 'left';
    stacked.forEach((label) => {
      const pillW = ctx.measureText(label.text).width + 12;
      ctx.strokeStyle = label.color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(w - padR, label.y);
      ctx.lineTo(w - padR + 6, label.drawY);
      ctx.stroke();
      ctx.fillStyle = label.color;
      ctx.beginPath();
      ctx.roundRect(w - padR + 6, label.drawY - 8, pillW, 16, 8);
      ctx.fill();
      ctx.fillStyle = '#ffffff';
      ctx.fillText(label.text, w - padR + 12, label.drawY + 3.5);
    });
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
    const { l: padL, r: padR } = PAD;
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
      const { l: padL, r: padR } = PAD;
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

  const canvasClass = [
    'chart-canvas',
    'replay-chart-canvas',
    isDragging ? 'replay-chart-canvas-dragging' : phase === 'selection' ? 'replay-chart-canvas-select' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className="chart-frame">
      <div className="chart-toolbar">
        <div className="replay-chart-actions">
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            onClick={() => setVisibleCount((prev) => Math.min(effectiveCandles.length + 30, Math.round(prev * 1.35)))}
            title="Thu nhỏ"
            aria-label="Thu nhỏ"
          >
            −
          </button>
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            onClick={() => setVisibleCount((prev) => Math.max(15, Math.round(prev * 0.75)))}
            title="Phóng to"
            aria-label="Phóng to"
          >
            +
          </button>
          <button
            type="button"
            className="btn btn-quiet btn-sm"
            onClick={() => {
              setVisibleCount(Math.min(effectiveCandles.length, 100) || 60);
              setOffsetRight(0);
            }}
            title="Đặt lại khung nhìn"
          >
            Đặt lại
          </button>
        </div>
        {phase === 'selection' && <span>Cuộn để zoom · Kéo để di chuyển · Bấm vào nến để chọn</span>}
      </div>

      <canvas
        ref={canvasRef}
        className={canvasClass}
        width={960}
        height={height}
        style={{ height }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
      />
    </div>
  );
}
