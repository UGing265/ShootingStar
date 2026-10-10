'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { CandleDTO, SnapshotSummary } from '../data/types';
import { SimulationJobResponse } from './types';
import { ExternalAnalysisJobDTO, ExternalContextVariant } from './external-types';

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

function formatForDateTimeLocalUtc7(ms: number): string {
  if (!ms || isNaN(ms)) return '';
  const d = new Date(ms + 7 * 3600 * 1000);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

function parseDateTimeLocalUtc7(val: string): number {
  if (!val) return 0;
  const [datePart, timePart] = val.split('T');
  if (!datePart || !timePart) return 0;
  const [y, m, d] = datePart.split('-').map(Number);
  const [hh, mm] = timePart.split(':').map(Number);
  return Date.UTC(y, m - 1, d, hh - 7, mm, 0, 0);
}

export function ReplayPlayer({
  snapshots,
}: {
  snapshots: SnapshotSummary[];
}) {
  const [activeTab, setActiveTab] = useState<'step1' | 'step2' | 'step3' | 'step4'>('step1');
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string>(snapshots[0]?.id || '');
  const [candles, setCandles] = useState<CandleDTO[]>([]);
  const [isLoadingCandles, setIsLoadingCandles] = useState<boolean>(false);

  // Engine & Model selection
  const [engineType, setEngineType] = useState<'external' | 'local'>('external');
  const [useMockMode, setUseMockMode] = useState<boolean>(true);
  const [contextVariant, setContextVariant] = useState<ExternalContextVariant>('A');

  // Purchase point state
  const [buyTimeMs, setBuyTimeMs] = useState<number>(0);
  const [buyPriceInput, setBuyPriceInput] = useState<string>('');
  const [manualDateTime, setManualDateTime] = useState<string>('');
  const [horizonMinutes, setHorizonMinutes] = useState<number>(30);

  // Pan & Zoom state
  const [visibleCount, setVisibleCount] = useState<number>(100);
  const [offsetRight, setOffsetRight] = useState<number>(0);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartXRef = useRef<number>(0);
  const dragStartOffsetRef = useRef<number>(0);
  const hasDraggedRef = useRef<boolean>(false);

  const { visibleCandles, startIndex, endIndex } = useMemo(() => {
    if (candles.length === 0) return { visibleCandles: [], startIndex: 0, endIndex: 0 };
    const end = Math.max(0, candles.length - offsetRight);
    const start = Math.max(0, end - visibleCount);
    return {
      visibleCandles: candles.slice(start, end),
      startIndex: start,
      endIndex: end,
    };
  }, [candles, visibleCount, offsetRight]);

  // Jobs state: support both external Gemini job and legacy simulation job
  const [externalJob, setExternalJob] = useState<ExternalAnalysisJobDTO | null>(null);
  const [simulationJob, setSimulationJob] = useState<SimulationJobResponse | null>(null);
  const [isLoadingJob, setIsLoadingJob] = useState<boolean>(false);
  const [isVoting, setIsVoting] = useState<boolean>(false);
  const [isRevealing, setIsRevealing] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Causal 6-hour history check
  const { causalCoverageHours, isCausalValid } = useMemo(() => {
    if (!buyTimeMs || candles.length === 0) {
      return { causalCoverageHours: 0, isCausalValid: false };
    }
    const priorCandles = candles.filter((c) => c.close_time_ms <= buyTimeMs);
    if (priorCandles.length === 0) {
      return { causalCoverageHours: 0, isCausalValid: false };
    }
    const earliestOpen = priorCandles[0].open_time_ms;
    const durationMs = buyTimeMs - earliestOpen;
    const hours = durationMs / (3600 * 1000);
    return {
      causalCoverageHours: hours,
      isCausalValid: hours >= 5.95, // Allow slight micro-margin
    };
  }, [buyTimeMs, candles]);

  // Load candles when selected snapshot changes
  useEffect(() => {
    if (!selectedSnapshotId) return;
    let isCancelled = false;
    setIsLoadingCandles(true);
    setErrorMsg(null);

    fetch(`/api/snapshots/${selectedSnapshotId}/candles?limit=300`)
      .then(async (res) => {
        if (!res.ok) {
          const errData = await res.json().catch(() => null);
          throw new Error(errData?.error || `Không thể tải danh sách nến (Mã lỗi ${res.status})`);
        }
        return res.json();
      })
      .then((data: CandleDTO[]) => {
        if (isCancelled) return;
        setCandles(data);
        setVisibleCount(Math.min(data.length, 100) || 60);
        setOffsetRight(0);
        if (data.length > 0) {
          // Default pick candle at 75% index to ensure ~6h of history prior to t
          const pickIdx = Math.min(data.length - 1, Math.max(0, Math.floor(data.length * 0.75)));
          const initialCandle = data[pickIdx];
          setBuyTimeMs(initialCandle.close_time_ms);
          setManualDateTime(formatForDateTimeLocalUtc7(initialCandle.close_time_ms));
          setBuyPriceInput(initialCandle.close.toString());
        }
      })
      .catch((err: unknown) => {
        if (isCancelled) return;
        setErrorMsg(err instanceof Error ? err.message : 'Lỗi tải nến');
      })
      .finally(() => {
        if (!isCancelled) setIsLoadingCandles(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedSnapshotId]);

  // Canvas zoom via mouse wheel
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      setVisibleCount((prev) => {
        if (e.deltaY < 0) {
          return Math.max(15, Math.round(prev * 0.82));
        } else {
          return Math.min(candles.length, Math.max(prev + 5, Math.round(prev * 1.22)));
        }
      });
    };

    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', handleWheel);
  }, [candles.length]);

  // Global mouse up
  useEffect(() => {
    const handleGlobalMouseUp = () => {
      setIsDragging(false);
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
  }, []);

  // Draw chart
  const drawChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || visibleCandles.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const padL = 60;
    const padR = 40;
    const padT = 30;
    const padB = 40;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    let minP = Math.min(...visibleCandles.map((c) => c.low));
    let maxP = Math.max(...visibleCandles.map((c) => c.high));

    const currentBuyPrice = parseFloat(buyPriceInput);
    if (!isNaN(currentBuyPrice) && currentBuyPrice > 0) {
      minP = Math.min(minP, currentBuyPrice * 0.998);
      maxP = Math.max(maxP, currentBuyPrice * 1.002);
    }

    const priceSpan = Math.max(maxP - minP, 1);
    const n = visibleCandles.length;
    const stepX = plotW / Math.max(n, 1);
    const candleW = Math.max(2, stepX * 0.7);

    // Background grid
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

    // Render candles
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

      // Selected buy candle marker
      if (Math.abs(c.close_time_ms - buyTimeMs) < 60000 || Math.abs(c.open_time_ms - buyTimeMs) < 60000) {
        selectedMarkerX = x;
        selectedMarkerY = closeY;
      }
    });

    // Time labels at bottom
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    const labelStep = Math.max(1, Math.floor(visibleCandles.length / 5));
    for (let i = 0; i < visibleCandles.length; i += labelStep) {
      const c = visibleCandles[i];
      const x = padL + i * stepX + stepX / 2;
      const d = new Date(c.close_time_ms + 7 * 3600 * 1000);
      const timeStr = `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
      ctx.fillText(timeStr, x, h - 12);
    }

    // UTC+7 indicator
    ctx.fillStyle = '#64748b';
    ctx.font = 'bold 9px monospace';
    ctx.textAlign = 'right';
    ctx.fillText('UTC+7', w - padR + 32, h - 12);

    // Horizontal Buy Price Line
    if (!isNaN(currentBuyPrice) && currentBuyPrice > 0) {
      const lineY = padT + ((maxP - currentBuyPrice) / priceSpan) * plotH;
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
      ctx.fillText(`Điểm mua giả định: $${currentBuyPrice.toLocaleString()}`, padL + 8, lineY - 6);
    }

    // Dot Marker on Chart
    if (selectedMarkerX !== null) {
      const targetMarkerY = !isNaN(currentBuyPrice) && currentBuyPrice > 0
        ? padT + ((maxP - currentBuyPrice) / priceSpan) * plotH
        : (selectedMarkerY || padT + plotH / 2);

      ctx.beginPath();
      ctx.arc(selectedMarkerX, targetMarkerY, 8, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(37, 99, 235, 0.25)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(selectedMarkerX, targetMarkerY, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#2563eb';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }, [visibleCandles, buyTimeMs, buyPriceInput]);

  useEffect(() => {
    drawChart();
  }, [drawChart]);

  // Pan & Click handlers
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
    const padR = 40;
    const plotW = canvas.width - padL - padR;
    const slotWidth = plotW / Math.max(1, visibleCandles.length);
    const candleShift = Math.round((deltaX * scaleX) / Math.max(1, slotWidth));
    const maxOffset = Math.max(0, candles.length - visibleCount);
    const newOffset = Math.max(0, Math.min(maxOffset, dragStartOffsetRef.current + candleShift));
    setOffsetRight(newOffset);
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(false);
    if (!hasDraggedRef.current) {
      const canvas = canvasRef.current;
      if (!canvas || visibleCandles.length === 0) return;
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const padL = 60;
      const padR = 40;
      const plotW = canvas.width - padL - padR;
      const relX = (x / rect.width) * canvas.width - padL;
      if (relX < 0 || relX > plotW) return;

      const stepX = plotW / Math.max(visibleCandles.length, 1);
      const idx = Math.min(Math.max(0, Math.floor(relX / stepX)), visibleCandles.length - 1);
      const picked = visibleCandles[idx];
      setBuyTimeMs(picked.close_time_ms);
      setManualDateTime(formatForDateTimeLocalUtc7(picked.close_time_ms));
      setBuyPriceInput(picked.close.toString());
    }
  };

  // Step 1 -> Step 2: Create Job
  const handleRunAIJob = async () => {
    setErrorMsg(null);
    const parsedPrice = parseFloat(buyPriceInput);
    if (isNaN(parsedPrice) || parsedPrice <= 0) {
      setErrorMsg('Vui lòng nhập giá mua hợp lệ (> 0).');
      return;
    }
    if (!buyTimeMs) {
      setErrorMsg('Vui lòng chọn thời điểm mua trên biểu đồ hoặc danh sách.');
      return;
    }

    if (engineType === 'external' && !isCausalValid) {
      setErrorMsg('Không đủ 6 giờ lịch sử trước mốc mua để đảm bảo tính nhân quả (Causal 6h Invariant).');
      return;
    }

    setIsLoadingJob(true);
    try {
      if (engineType === 'external') {
        const res = await fetch('/api/external-analysis/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            snapshot_id: selectedSnapshotId,
            prediction_time_t_ms: buyTimeMs,
            purchase_price_p: parsedPrice,
            horizon_minutes: horizonMinutes,
            context_variant: contextVariant,
            mode: 'RETROSPECTIVE',
            mock_mode: useMockMode,
          }),
        });

        const data = await res.json();
        if (!res.ok) {
          setErrorMsg(data.error || 'Không thể tạo tác vụ phân tích Gemini.');
          return;
        }

        setExternalJob(data);
        setSimulationJob(null);
        setActiveTab('step2');
      } else {
        const res = await fetch('/api/replay/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            snapshot_id: selectedSnapshotId,
            buy_time_ms: buyTimeMs,
            buy_price: parsedPrice,
            horizon_minutes: horizonMinutes,
          }),
        });

        const data = await res.json();
        if (!res.ok) {
          setErrorMsg(data.error || 'Không thể tạo tác vụ mô phỏng cục bộ.');
          return;
        }

        setSimulationJob(data);
        setExternalJob(null);
        setActiveTab('step2');
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Lỗi kết nối khi gửi yêu cầu phân tích.');
    } finally {
      setIsLoadingJob(false);
    }
  };

  // Step 3: Vote UP/DOWN
  const handleVote = async (direction: 'UP' | 'DOWN') => {
    setErrorMsg(null);
    setIsVoting(true);
    try {
      if (externalJob) {
        const res = await fetch(`/api/external-analysis/jobs/${externalJob.id}/vote`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ vote: direction }),
        });
        const data = await res.json();
        if (!res.ok) {
          setErrorMsg(data.error || 'Không thể lưu dự đoán cá nhân.');
          return;
        }
        setExternalJob(data);
      } else if (simulationJob) {
        const res = await fetch(`/api/replay/jobs/${simulationJob.job_id}/vote`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_direction: direction }),
        });
        const data = await res.json();
        if (!res.ok) {
          setErrorMsg(data.error || 'Không thể lưu dự đoán.');
          return;
        }
        setSimulationJob(data);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Lỗi gửi dự đoán.');
    } finally {
      setIsVoting(false);
    }
  };

  // Step 4: Reveal Outcome
  const handleRevealOutcome = async () => {
    setErrorMsg(null);
    setIsRevealing(true);
    try {
      if (externalJob) {
        const res = await fetch(`/api/external-analysis/jobs/${externalJob.id}/reveal`, {
          method: 'POST',
        });
        const data = await res.json();
        if (!res.ok) {
          setErrorMsg(data.error || 'Không thể mở kết quả thực tế.');
          return;
        }
        setExternalJob(data);
      } else if (simulationJob) {
        const res = await fetch(`/api/replay/jobs/${simulationJob.job_id}/reveal`, {
          method: 'POST',
        });
        const data = await res.json();
        if (!res.ok) {
          setErrorMsg(data.error || 'Không thể mở kết quả.');
          return;
        }
        setSimulationJob(data);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Lỗi kết nối khi xem kết quả.');
    } finally {
      setIsRevealing(false);
    }
  };

  // Reset
  const handleResetSimulation = () => {
    setExternalJob(null);
    setSimulationJob(null);
    setActiveTab('step1');
  };

  const hasJob = externalJob !== null || simulationJob !== null;
  const hasUserVote = (externalJob?.user_vote != null) || (simulationJob?.user_vote != null);
  const hasOutcome = (externalJob?.outcome != null) || (simulationJob?.outcome != null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 4-Step Nav Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 12,
          background: '#ffffff',
          padding: '12px 16px',
          borderRadius: 8,
          border: '1px solid #e2e8f0',
        }}
      >
        {[
          { key: 'step1', num: '1', title: 'Điểm mua & Causal 6h' },
          { key: 'step2', num: '2', title: 'Dự báo của AI' },
          { key: 'step3', num: '3', title: 'Dự đoán của tôi' },
          { key: 'step4', num: '4', title: 'Kết quả & Đối chiếu' },
        ].map((s) => {
          const isActive = activeTab === s.key;
          const isDone =
            (s.key === 'step1' && hasJob) ||
            (s.key === 'step2' && hasJob) ||
            (s.key === 'step3' && hasUserVote) ||
            (s.key === 'step4' && hasOutcome);

          return (
            <button
              key={s.key}
              type="button"
              onClick={() => {
                if (s.key === 'step1') setActiveTab('step1');
                if (s.key === 'step2' && hasJob) setActiveTab('step2');
                if (s.key === 'step3' && hasJob) setActiveTab('step3');
                if (s.key === 'step4' && hasUserVote) setActiveTab('step4');
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 12px',
                borderRadius: 6,
                border: isActive ? '2px solid #2563eb' : '1px solid #e2e8f0',
                background: isActive ? '#eff6ff' : isDone ? '#f8fafc' : '#ffffff',
                cursor: hasJob || s.key === 'step1' ? 'pointer' : 'not-allowed',
                textAlign: 'left',
              }}
            >
              <span
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: 12,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 12,
                  fontWeight: 700,
                  background: isActive ? '#2563eb' : isDone ? '#16a34a' : '#cbd5e1',
                  color: '#ffffff',
                }}
              >
                {isDone && !isActive ? '✓' : s.num}
              </span>
              <span style={{ fontSize: 13, fontWeight: isActive ? 600 : 500, color: isActive ? '#1d4ed8' : '#334155' }}>
                {s.title}
              </span>
            </button>
          );
        })}
      </div>

      {/* Global Error Banner */}
      {errorMsg && (
        <div style={{ padding: '10px 16px', background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 6, color: '#b91c1c', fontSize: 13 }}>
          ⚠️ {errorMsg}
        </div>
      )}

      {/* TAB 1: Điểm mua & Thiết lập */}
      {activeTab === 'step1' && (
        <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '20px' }}>
          {/* Header & Snapshot Selection */}
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 4px 0', color: '#0f172a' }}>
                Bước 1: Chọn Điểm mua & Kiểm tra Causal Context 6 Giờ
              </h2>
              <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
                Cuộn chuột để zoom, giữ chuột trái kéo để pan qua lại, click trực tiếp lên nến để chọn mốc mua.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Snapshot:</label>
              <select
                value={selectedSnapshotId}
                onChange={(e) => setSelectedSnapshotId(e.target.value)}
                style={{ padding: '6px 12px', fontSize: 13, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6 }}
              >
                {snapshots.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.symbol} ({s.timeframe}) — {s.candle_count} nến ({formatUtc7(s.start_time_ms).slice(0, 16)})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Canvas Chart Area */}
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
                background: 'rgba(255, 255, 255, 0.9)',
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
                onClick={() => setVisibleCount((prev) => Math.min(candles.length, Math.round(prev * 1.35)))}
                title="Thu nhỏ (Zoom Out)"
                style={{ padding: '3px 8px', fontSize: 12, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 4, cursor: 'pointer' }}
              >
                −
              </button>
              <button
                type="button"
                onClick={() => {
                  setVisibleCount(Math.min(candles.length, 100) || 60);
                  setOffsetRight(0);
                }}
                title="Đặt lại khung nhìn"
                style={{ padding: '3px 8px', fontSize: 11, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 4, cursor: 'pointer' }}
              >
                ⟲ Reset
              </button>
            </div>

            {isLoadingCandles && (
              <div style={{ position: 'absolute', top: '50%', left: '42%', fontSize: 14, color: '#64748b', fontWeight: 600 }}>
                ⏳ Đang tải nến snapshot...
              </div>
            )}
            <canvas
              ref={canvasRef}
              width={960}
              height={360}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              style={{ width: '100%', height: '360px', cursor: isDragging ? 'grabbing' : 'crosshair', display: 'block', userSelect: 'none' }}
            />
          </div>

          {/* Engine Selector & External Analysis Controls */}
          <div
            style={{
              marginTop: 18,
              padding: '16px',
              borderRadius: 6,
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            {/* Engine Tabs */}
            <div>
              <label style={{ fontSize: 12, fontWeight: 700, color: '#1e293b', display: 'block', marginBottom: 6 }}>
                CHỌN MÔ HÌNH PHÂN TÍCH:
              </label>
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setEngineType('external')}
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: 6,
                    border: engineType === 'external' ? '2px solid #2563eb' : '1px solid #cbd5e1',
                    background: engineType === 'external' ? '#eff6ff' : '#ffffff',
                    color: engineType === 'external' ? '#1d4ed8' : '#334155',
                    fontWeight: engineType === 'external' ? 700 : 500,
                    fontSize: 13,
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>🤖</span>
                    <span>Gemini 2.5 Flash / External Analysis</span>
                    <span style={{ fontSize: 10, background: '#dbeafe', color: '#1e40af', padding: '1px 6px', borderRadius: 4 }}>
                      Khuyên dùng
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                    Gửi 6 giờ nến sạch trước mốc t, trích xuất nhận định lý do, nến viện dẫn và bài học.
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setEngineType('local')}
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: 6,
                    border: engineType === 'local' ? '2px solid #2563eb' : '1px solid #cbd5e1',
                    background: engineType === 'local' ? '#eff6ff' : '#ffffff',
                    color: engineType === 'local' ? '#1d4ed8' : '#334155',
                    fontWeight: engineType === 'local' ? 700 : 500,
                    fontSize: 13,
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>⚙️</span>
                    <span>Mô hình Cục bộ (Point-Price Pipeline)</span>
                    <span style={{ fontSize: 10, background: '#fee2e2', color: '#991b1b', padding: '1px 6px', borderRadius: 4 }}>
                      Gated
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                    Đang ở trạng thái an toàn: từ chối ngoại suy xác suất khi chưa có model OOS.
                  </div>
                </button>
              </div>
            </div>

            {/* External Options (Mock & Variant) */}
            {engineType === 'external' && (
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  padding: '12px 14px',
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 6,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600, color: '#334155' }}>
                    <input
                      type="checkbox"
                      checked={useMockMode}
                      onChange={(e) => setUseMockMode(e.target.checked)}
                      style={{ cursor: 'pointer' }}
                    />
                    <span>Chế độ Mock (Thử nghiệm miễn phí, không tốn quota Google)</span>
                  </label>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Cấu trúc nến gửi AI:</span>
                  <button
                    type="button"
                    onClick={() => setContextVariant('A')}
                    style={{
                      padding: '4px 10px',
                      fontSize: 12,
                      borderRadius: 4,
                      border: contextVariant === 'A' ? '1px solid #2563eb' : '1px solid #cbd5e1',
                      background: contextVariant === 'A' ? '#2563eb' : '#ffffff',
                      color: contextVariant === 'A' ? '#ffffff' : '#334155',
                      fontWeight: contextVariant === 'A' ? 600 : 400,
                      cursor: 'pointer',
                    }}
                  >
                    Variant A (6h OHLCV thuần)
                  </button>
                  <button
                    type="button"
                    onClick={() => setContextVariant('B')}
                    style={{
                      padding: '4px 10px',
                      fontSize: 12,
                      borderRadius: 4,
                      border: contextVariant === 'B' ? '1px solid #2563eb' : '1px solid #cbd5e1',
                      background: contextVariant === 'B' ? '#2563eb' : '#ffffff',
                      color: contextVariant === 'B' ? '#ffffff' : '#334155',
                      fontWeight: contextVariant === 'B' ? 600 : 400,
                      cursor: 'pointer',
                    }}
                  >
                    Variant B (+ Chỉ số kỹ thuật)
                  </button>
                </div>
              </div>
            )}

            {/* Causal 6h Invariant Status Banner */}
            {engineType === 'external' && (
              <div
                style={{
                  padding: '10px 14px',
                  borderRadius: 6,
                  border: isCausalValid ? '1px solid #bbf7d0' : '1px solid #fed7aa',
                  background: isCausalValid ? '#f0fdf4' : '#fff7ed',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 16 }}>{isCausalValid ? '🛡️' : '⚠️'}</span>
                  <span style={{ fontSize: 13, color: isCausalValid ? '#166534' : '#9a3412', fontWeight: 500 }}>
                    {isCausalValid ? (
                      <>
                        <strong>Đảm bảo Causal Context:</strong> Có đủ <strong>{causalCoverageHours.toFixed(1)} giờ</strong> nến sạch trước mốc t (yêu cầu tối thiểu 6.0 giờ).
                      </>
                    ) : (
                      <>
                        <strong>Thiếu lịch sử 6 giờ:</strong> Đoạn nến trước mốc t chỉ dài <strong>{causalCoverageHours.toFixed(1)}/6.0 giờ</strong>. Hệ thống từ chối gọi API để tránh vi phạm tính nhân quả.
                      </>
                    )}
                  </span>
                </div>
                {!isCausalValid && (
                  <span style={{ fontSize: 12, color: '#c2410c', fontWeight: 600 }}>
                    Vui lòng chọn mốc t muộn hơn hoặc nạp snapshot dài hơn
                  </span>
                )}
              </div>
            )}

            {/* Inputs: Time, Price, Horizon */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: 16,
              }}
            >
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
                  MỐC THỜI GIAN MUA (t - UTC+7):
                </label>
                <input
                  type="datetime-local"
                  value={manualDateTime}
                  onChange={(e) => {
                    setManualDateTime(e.target.value);
                    const parsed = parseDateTimeLocalUtc7(e.target.value);
                    setBuyTimeMs(parsed > 0 ? parsed : 0);
                  }}
                  style={{ width: '100%', padding: '8px 10px', fontSize: 13, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, fontFamily: 'monospace' }}
                />
                <span style={{ fontSize: 11, color: '#64748b', display: 'block', marginTop: 4 }}>
                  {buyTimeMs ? `${formatUtc7(buyTimeMs)}` : 'Chưa chọn mốc thời gian'}
                </span>
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
                  GIÁ MUA GIẢ ĐỊNH ($):
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={buyPriceInput}
                  onChange={(e) => setBuyPriceInput(e.target.value)}
                  placeholder="Nhập giá mua..."
                  style={{ width: '100%', padding: '8px 10px', fontSize: 13, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, fontWeight: 600 }}
                />
                {(() => {
                  const matchingCandle = candles.filter((c) => c.close_time_ms <= buyTimeMs).slice(-1)[0] || null;
                  const observedClose = matchingCandle ? matchingCandle.close : null;
                  if (observedClose === null) return null;
                  const diffPct = !isNaN(parseFloat(buyPriceInput)) && parseFloat(buyPriceInput) > 0
                    ? ((parseFloat(buyPriceInput) - observedClose) / observedClose * 100)
                    : 0;
                  return (
                    <span style={{ fontSize: 11, color: '#64748b', display: 'block', marginTop: 4 }}>
                      Giá nến đóng quan sát: ${observedClose.toLocaleString()}
                      {Math.abs(diffPct) > 0.001 && (
                        <strong style={{ color: '#d97706', display: 'block' }}>
                          (Lệch giá nến: {diffPct > 0 ? `+${diffPct.toFixed(2)}%` : `${diffPct.toFixed(2)}%`})
                        </strong>
                      )}
                    </span>
                  );
                })()}
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
                  THỜI LƯỢNG DỰ BÁO (HORIZON):
                </label>
                <div style={{ display: 'flex', gap: 6 }}>
                  {[
                    { m: 30, label: '30m' },
                    { m: 60, label: '1h' },
                    { m: 240, label: '4h' },
                    { m: 1440, label: '24h' },
                  ].map((h) => (
                    <button
                      key={h.m}
                      type="button"
                      disabled={engineType === 'external' && h.m !== 30}
                      onClick={() => setHorizonMinutes(h.m)}
                      title={engineType === 'external' && h.m !== 30 ? 'Gemini External Analysis hiện khóa ở horizon 30m cho pilot' : ''}
                      style={{
                        flex: 1,
                        padding: '8px 0',
                        fontSize: 12,
                        fontWeight: horizonMinutes === h.m ? 700 : 500,
                        background: horizonMinutes === h.m ? '#2563eb' : '#ffffff',
                        color: horizonMinutes === h.m ? '#ffffff' : (engineType === 'external' && h.m !== 30) ? '#94a3b8' : '#334155',
                        border: horizonMinutes === h.m ? '1px solid #2563eb' : '1px solid #cbd5e1',
                        borderRadius: 4,
                        cursor: (engineType === 'external' && h.m !== 30) ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {h.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div style={{ marginTop: 18, display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={handleRunAIJob}
              disabled={isLoadingJob || !buyTimeMs || !buyPriceInput || (engineType === 'external' && !isCausalValid)}
              style={{
                padding: '10px 24px',
                fontSize: 14,
                fontWeight: 600,
                background: (isLoadingJob || !buyTimeMs || (engineType === 'external' && !isCausalValid)) ? '#94a3b8' : '#2563eb',
                color: '#ffffff',
                border: 'none',
                borderRadius: 6,
                cursor: (isLoadingJob || !buyTimeMs || (engineType === 'external' && !isCausalValid)) ? 'not-allowed' : 'pointer',
              }}
            >
              {isLoadingJob
                ? '⏳ Đang trích xuất 6h Causal & Phân tích...'
                : engineType === 'external'
                ? '▶️ Phân tích với Gemini (Step 2)'
                : '▶️ Chạy tác vụ Mô phỏng Cục bộ (Step 2)'}
            </button>
          </div>
        </div>
      )}

      {/* TAB 2: Dự báo của AI */}
      {activeTab === 'step2' && (externalJob || simulationJob) && (
        <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '20px' }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 4px 0', color: '#0f172a' }}>
            Bước 2: Kết quả nhận định từ Mô hình AI
          </h2>
          <p style={{ margin: '0 0 16px 0', fontSize: 13, color: '#64748b' }}>
            Mô hình được cung cấp strictly các nến lịch sử có thời gian khả dụng ≤ mốc mua (Zero-Lookahead Causal Window).
          </p>

          {/* Job Overview Specs */}
          <div
            style={{
              padding: '14px',
              borderRadius: 6,
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 12,
              marginBottom: 16,
            }}
          >
            <div>
              <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>MỐC MUA (t)</span>
              <strong style={{ fontSize: 13 }}>
                {formatUtc7(externalJob ? externalJob.prediction_time_t_ms : simulationJob!.buy_time_ms)}
              </strong>
            </div>
            <div>
              <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>GIÁ MUA GIẢ ĐỊNH (P)</span>
              <strong style={{ fontSize: 13 }}>
                ${(externalJob ? externalJob.purchase_price_p : simulationJob!.buy_price).toLocaleString()}
              </strong>
            </div>
            <div>
              <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>HORIZON DỰ ĐOÁN</span>
              <strong style={{ fontSize: 13 }}>
                {externalJob ? externalJob.horizon_minutes : simulationJob!.horizon_minutes} phút
              </strong>
            </div>
            {externalJob && (
              <div>
                <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>BIẾN THỂ CONTEXT</span>
                <strong style={{ fontSize: 13 }}>
                  Variant {externalJob.context_variant} ({externalJob.mode})
                </strong>
              </div>
            )}
          </div>

          {/* EXTERNAL GEMINI ANALYSIS VIEW */}
          {externalJob && (
            <div>
              {/* Lookahead Risk Banner */}
              {externalJob.leakage_risk_banner && (
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: 6,
                    background: '#fffbeb',
                    border: '1px solid #fef3c7',
                    marginBottom: 16,
                    color: '#92400e',
                    fontSize: 13,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                  }}
                >
                  <span style={{ fontSize: 18 }}>⚠️</span>
                  <div>
                    <strong>Cảnh báo Hồi cứu:</strong> Nhận định API thử nghiệm — không phải dự báo đã kiểm định.
                    Model hiện nay có thể đã được huấn luyện với thông tin sau mốc lịch sử này.
                  </div>
                </div>
              )}

              {/* Prediction Direction Box */}
              <div
                style={{
                  padding: '18px',
                  borderRadius: 8,
                  border:
                    externalJob.ai_prediction?.direction === 'UP'
                      ? '2px solid #16a34a'
                      : externalJob.ai_prediction?.direction === 'DOWN'
                      ? '2px solid #dc2626'
                      : '2px solid #f59e0b',
                  background:
                    externalJob.ai_prediction?.direction === 'UP'
                      ? '#f0fdf4'
                      : externalJob.ai_prediction?.direction === 'DOWN'
                      ? '#fef2f2'
                      : '#fffbeb',
                  marginBottom: 18,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#334155' }}>
                    NHẬN ĐỊNH HƯỚNG GIÁ TỪ MODEL
                  </span>
                  <span style={{ fontSize: 12, padding: '3px 8px', borderRadius: 4, background: '#ffffff', border: '1px solid #cbd5e1', color: '#475569' }}>
                    Model: {externalJob.ai_prediction?.model_id} (Prompt {externalJob.ai_prediction?.prompt_version})
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14 }}>
                  <div
                    style={{
                      padding: '10px 20px',
                      borderRadius: 6,
                      background:
                        externalJob.ai_prediction?.direction === 'UP'
                          ? '#16a34a'
                          : externalJob.ai_prediction?.direction === 'DOWN'
                          ? '#dc2626'
                          : '#d97706',
                      color: '#ffffff',
                      fontWeight: 700,
                      fontSize: 16,
                    }}
                  >
                    {externalJob.ai_prediction?.direction === 'UP' && '▲ DỰ BÁO TĂNG (UP)'}
                    {externalJob.ai_prediction?.direction === 'DOWN' && '▼ DỰ BÁO GIẢM (DOWN)'}
                    {externalJob.ai_prediction?.direction === 'ABSTAIN' && '⏸ KHÔNG DỰ BÁO (ABSTAIN)'}
                  </div>
                  <div style={{ fontSize: 13, color: '#475569' }}>
                    Trạng thái: <strong>{externalJob.status}</strong> (Xác suất định lượng: <em>Chưa hiệu chuẩn</em>)
                  </div>
                </div>

                {/* AI Rationale */}
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 6, padding: '12px 14px', marginBottom: 12 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
                    Lý lẽ giải thích (AI viết):
                  </span>
                  <p style={{ margin: 0, fontSize: 14, color: '#1e293b', lineHeight: 1.5 }}>
                    {externalJob.ai_prediction?.rationale || 'Không có lý lẽ từ model.'}
                  </p>
                </div>

                {/* Evidence timestamps */}
                {externalJob.ai_prediction?.evidence_candle_times && externalJob.ai_prediction.evidence_candle_times.length > 0 && (
                  <div style={{ marginBottom: 10 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
                      Mốc nến AI viện dẫn làm bằng chứng:
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {externalJob.ai_prediction.evidence_candle_times.map((t, idx) => (
                        <span key={idx} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: '#e2e8f0', color: '#334155', fontFamily: 'monospace' }}>
                          {formatUtc7(t)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Referenced Lessons */}
                {externalJob.ai_prediction?.lesson_ids && externalJob.ai_prediction.lesson_ids.length > 0 && (
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
                      Bài học trading đã duyệt được tham chiếu:
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                      {externalJob.ai_prediction.lesson_ids.map((lid, idx) => (
                        <a
                          key={idx}
                          href="/lessons/review"
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            fontSize: 12,
                            padding: '3px 10px',
                            borderRadius: 4,
                            background: '#eff6ff',
                            border: '1px solid #bfdbfe',
                            color: '#1d4ed8',
                            textDecoration: 'none',
                            fontWeight: 600,
                          }}
                        >
                          📖 {lid}
                        </a>
                      ))}
                      <span style={{ fontSize: 11, color: '#64748b' }}>
                        (Link giải thích khái niệm, không bảo đảm thắng)
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* LEGACY LOCAL PREDICTION BOX */}
          {simulationJob && (
            <div
              style={{
                padding: '18px',
                borderRadius: 8,
                border: simulationJob.ai_prediction?.predicted_direction === 'NO_MODEL' ? '1px solid #fef3c7' : '1px solid #bbf7d0',
                background: simulationJob.ai_prediction?.predicted_direction === 'NO_MODEL' ? '#fffbeb' : '#f0fdf4',
                marginBottom: 18,
              }}
            >
              {simulationJob.ai_prediction?.predicted_direction === 'NO_MODEL' ? (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontSize: 16 }}>⚠️</span>
                    <strong style={{ fontSize: 14, color: '#92400e' }}>Chưa có mô hình nội bộ thỏa mãn kiểm định ngoài OOS</strong>
                  </div>
                  <p style={{ margin: '0 0 8px 0', fontSize: 13, color: '#78350f' }}>
                    {simulationJob.ai_prediction.evidence_summary}
                  </p>
                  <span style={{ fontSize: 11, color: '#b45309' }}>
                    Chính sách độ chính xác: Hệ thống từ chối bịa đặt xác suất khi chưa có model được kiểm định thỏa mãn cutoff trước mốc mua.
                  </span>
                </div>
              ) : (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#166534' }}>
                      DỰ BÁO XÁC SUẤT ĐÃ ĐƯỢC HIỆU CHUẨN
                    </span>
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>
                    {simulationJob.ai_prediction?.predicted_direction}
                  </div>
                </div>
              )}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <button
              type="button"
              onClick={() => setActiveTab('step1')}
              style={{ padding: '8px 16px', fontSize: 13, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, cursor: 'pointer' }}
            >
              ← Quay lại Bước 1
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('step3')}
              style={{ padding: '8px 20px', fontSize: 14, fontWeight: 600, background: '#2563eb', color: '#ffffff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
            >
              Tiếp tục: Nhập dự đoán của bạn (Step 3) →
            </button>
          </div>
        </div>
      )}

      {/* TAB 3: Dự đoán của tôi */}
      {activeTab === 'step3' && (externalJob || simulationJob) && (
        <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '20px' }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 4px 0', color: '#0f172a' }}>
            Bước 3: Dự đoán cá nhân của bạn (User Prediction)
          </h2>
          <p style={{ margin: '0 0 16px 0', fontSize: 13, color: '#64748b' }}>
            Bạn đã thấy nhận định của AI. Hãy chọn UP hoặc DOWN theo nhận định của riêng bạn. Lựa chọn này được lưu độc lập, bất biến và AI không học từ lựa chọn này.
          </p>

          {hasUserVote ? (
            <div
              style={{
                padding: '16px',
                borderRadius: 8,
                background: '#f0fdf4',
                border: '1px solid #bbf7d0',
                marginBottom: 20,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 18 }}>🔒</span>
                <div>
                  <strong style={{ fontSize: 14, color: '#166534' }}>
                    Dự đoán của bạn đã được niêm phong: {externalJob ? (externalJob.user_vote === 'UP' ? '▲ TĂNG (UP)' : '▼ GIẢM (DOWN)') : (simulationJob?.user_vote?.user_direction === 'UP' ? '▲ TĂNG (UP)' : '▼ GIẢM (DOWN)')}
                  </strong>
                  <span style={{ display: 'block', fontSize: 12, color: '#15803d', marginTop: 2 }}>
                    Đã khóa an toàn vào cơ sở dữ liệu.
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
              <button
                type="button"
                onClick={() => handleVote('UP')}
                disabled={isVoting}
                style={{
                  flex: 1,
                  padding: '20px',
                  borderRadius: 8,
                  border: '2px solid #16a34a',
                  background: '#f0fdf4',
                  color: '#15803d',
                  fontSize: 16,
                  fontWeight: 700,
                  cursor: isVoting ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <span style={{ fontSize: 24 }}>▲</span>
                <span>TÔI DỰ ĐOÁN: TĂNG (UP)</span>
                <span style={{ fontSize: 12, fontWeight: 400, color: '#166534' }}>
                  Giá sau 30 phút sẽ cao hơn ${((externalJob ? externalJob.purchase_price_p : simulationJob?.buy_price) || 0).toLocaleString()}
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleVote('DOWN')}
                disabled={isVoting}
                style={{
                  flex: 1,
                  padding: '20px',
                  borderRadius: 8,
                  border: '2px solid #dc2626',
                  background: '#fef2f2',
                  color: '#b91c1c',
                  fontSize: 16,
                  fontWeight: 700,
                  cursor: isVoting ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <span style={{ fontSize: 24 }}>▼</span>
                <span>TÔI DỰ ĐOÁN: GIẢM (DOWN)</span>
                <span style={{ fontSize: 12, fontWeight: 400, color: '#991b1b' }}>
                  Giá sau 30 phút sẽ thấp hơn ${((externalJob ? externalJob.purchase_price_p : simulationJob?.buy_price) || 0).toLocaleString()}
                </span>
              </button>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <button
              type="button"
              onClick={() => setActiveTab('step2')}
              style={{ padding: '8px 16px', fontSize: 13, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, cursor: 'pointer' }}
            >
              ← Quay lại Bước 2
            </button>
            {hasUserVote && (
              <button
                type="button"
                onClick={() => setActiveTab('step4')}
                style={{ padding: '8px 20px', fontSize: 14, fontWeight: 600, background: '#2563eb', color: '#ffffff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
              >
                Tiếp tục: Xem kết quả thực tế (Step 4) →
              </button>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Kết quả thực tế & Đối chiếu */}
      {activeTab === 'step4' && (externalJob || simulationJob) && (
        <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '20px' }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 4px 0', color: '#0f172a' }}>
            Bước 4: Kết quả thực tế của Thị trường & Đối chiếu hai bên
          </h2>
          <p style={{ margin: '0 0 16px 0', fontSize: 13, color: '#64748b' }}>
            Đối chiếu giá nến thực tế tại mốc t + 30m với giá mua giả định P để chấm điểm độc lập cho AI và bạn.
          </p>

          {!hasOutcome ? (
            <div
              style={{
                padding: '24px',
                textAlign: 'center',
                borderRadius: 8,
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                marginBottom: 20,
              }}
            >
              <p style={{ margin: '0 0 16px 0', fontSize: 14, color: '#475569' }}>
                Cả hai dự đoán (AI và Bạn) đã được niêm phong an toàn. Hãy mở phong ấn để đối chiếu với dữ liệu thị trường thực tế.
              </p>
              <button
                type="button"
                onClick={handleRevealOutcome}
                disabled={isRevealing}
                style={{
                  padding: '12px 28px',
                  fontSize: 15,
                  fontWeight: 700,
                  background: isRevealing ? '#94a3b8' : '#16a34a',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: 6,
                  cursor: isRevealing ? 'not-allowed' : 'pointer',
                }}
              >
                {isRevealing ? '⏳ Đang kiểm tra nến tương lai...' : '🔍 Xem Kết quả thực tế'}
              </button>
            </div>
          ) : (
            <div>
              {/* Outcome Market Metrics */}
              {externalJob ? (
                <div>
                  <div
                    style={{
                      padding: '16px',
                      borderRadius: 8,
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      marginBottom: 20,
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                      gap: 14,
                    }}
                  >
                    <div>
                      <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>GIÁ MUA BAN ĐẦU (P)</span>
                      <strong style={{ fontSize: 16 }}>${externalJob.purchase_price_p.toLocaleString()}</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>GIÁ THỰC TẾ SAU 30M</span>
                      <strong style={{ fontSize: 16 }}>
                        {externalJob.target_price ? `$${externalJob.target_price.toLocaleString()}` : 'N/A'}
                      </strong>
                    </div>
                    <div>
                      <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>CHIỀU THỊ TRƯỜNG</span>
                      <strong style={{ fontSize: 16 }}>
                        {externalJob.outcome === 'UP' && '▲ TĂNG (UP)'}
                        {externalJob.outcome === 'DOWN' && '▼ GIẢM (DOWN)'}
                        {externalJob.outcome === 'FLAT' && '— ĐI NGANG (FLAT)'}
                        {externalJob.outcome === 'UNSCORABLE' && '⚠️ KHÔNG THỂ CHẤM'}
                      </strong>
                    </div>
                  </div>

                  {/* Independent Scorecard Table */}
                  <div style={{ marginBottom: 20 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 10px 0', color: '#0f172a' }}>
                      Bảng điểm đối chiếu độc lập (Independent Scorecard)
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                      {/* AI Card */}
                      <div
                        style={{
                          padding: '16px',
                          borderRadius: 8,
                          border:
                            externalJob.outcome === externalJob.ai_prediction?.direction
                              ? '2px solid #16a34a'
                              : externalJob.ai_prediction?.direction === 'ABSTAIN'
                              ? '1px solid #cbd5e1'
                              : '2px solid #dc2626',
                          background:
                            externalJob.outcome === externalJob.ai_prediction?.direction
                              ? '#f0fdf4'
                              : externalJob.ai_prediction?.direction === 'ABSTAIN'
                              ? '#f8fafc'
                              : '#fef2f2',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <span style={{ fontWeight: 600, fontSize: 14 }}>🤖 Mô hình Gemini</span>
                          <span
                            style={{
                              fontSize: 12,
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 4,
                              background:
                                externalJob.outcome === externalJob.ai_prediction?.direction
                                  ? '#dcfce7'
                                  : externalJob.ai_prediction?.direction === 'ABSTAIN'
                                  ? '#e2e8f0'
                                  : '#fee2e2',
                              color:
                                externalJob.outcome === externalJob.ai_prediction?.direction
                                  ? '#166534'
                                  : externalJob.ai_prediction?.direction === 'ABSTAIN'
                                  ? '#475569'
                                  : '#991b1b',
                            }}
                          >
                            {externalJob.ai_prediction?.direction === 'ABSTAIN'
                              ? 'MIỄN CHẤM'
                              : externalJob.outcome === externalJob.ai_prediction?.direction
                              ? '✓ ĐÚNG'
                              : '✕ SAI'}
                          </span>
                        </div>
                        <div style={{ fontSize: 13, color: '#475569' }}>
                          Dự báo của AI: <strong>{externalJob.ai_prediction?.direction}</strong>
                        </div>
                      </div>

                      {/* User Card */}
                      <div
                        style={{
                          padding: '16px',
                          borderRadius: 8,
                          border:
                            externalJob.outcome === externalJob.user_vote
                              ? '2px solid #16a34a'
                              : '2px solid #dc2626',
                          background:
                            externalJob.outcome === externalJob.user_vote
                              ? '#f0fdf4'
                              : '#fef2f2',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <span style={{ fontWeight: 600, fontSize: 14 }}>👤 Bạn (User)</span>
                          <span
                            style={{
                              fontSize: 12,
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 4,
                              background:
                                externalJob.outcome === externalJob.user_vote
                                  ? '#dcfce7'
                                  : '#fee2e2',
                              color:
                                externalJob.outcome === externalJob.user_vote
                                  ? '#166534'
                                  : '#991b1b',
                            }}
                          >
                            {externalJob.outcome === externalJob.user_vote ? '✓ ĐÚNG' : '✕ SAI'}
                          </span>
                        </div>
                        <div style={{ fontSize: 13, color: '#475569' }}>
                          Lựa chọn của bạn: <strong>{externalJob.user_vote}</strong>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* Legacy simulation outcome */
                <div>
                  <div
                    style={{
                      padding: '16px',
                      borderRadius: 8,
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      marginBottom: 20,
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                      gap: 14,
                    }}
                  >
                    <div>
                      <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>GIÁ MUA BAN ĐẦU</span>
                      <strong style={{ fontSize: 16 }}>${simulationJob!.buy_price.toLocaleString()}</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>GIÁ SAU 30M</span>
                      <strong style={{ fontSize: 16 }}>
                        {simulationJob!.outcome?.future_price ? `$${simulationJob!.outcome!.future_price.toLocaleString()}` : 'N/A'}
                      </strong>
                    </div>
                    <div>
                      <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>CHIỀU THỊ TRƯỜNG</span>
                      <strong style={{ fontSize: 16 }}>
                        {simulationJob!.outcome?.market_direction === 'UP'
                          ? '▲ TĂNG (UP)'
                          : simulationJob!.outcome?.market_direction === 'DOWN'
                          ? '▼ GIẢM (DOWN)'
                          : '— ĐI NGANG'}
                      </strong>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
            <button
              type="button"
              onClick={() => setActiveTab('step3')}
              style={{ padding: '8px 16px', fontSize: 13, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, cursor: 'pointer' }}
            >
              ← Quay lại Bước 3
            </button>
            <button
              type="button"
              onClick={handleResetSimulation}
              style={{ padding: '8px 20px', fontSize: 13, fontWeight: 600, background: '#0f172a', color: '#ffffff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
            >
              🔄 Bắt đầu mô phỏng tại điểm khác
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
