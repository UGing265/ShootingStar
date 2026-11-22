'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CandleDTO, SnapshotSummary } from '../data/types';
import type { SimulationJobResponse } from './types';
import type { ExternalAnalysisJobDTO, ExternalContextVariant } from './external-types';
import { isInProgress } from '../report/labels';
import { saveRecentReport } from '../report/recent-reports';
import { formatDateTime } from '@/shared/format';
import { HORIZON_MINUTES, REQUIRED_HISTORY_HOURS, WINDOW_CANDLES, causalHours, defaultPickIndex, windowStartMs } from './replay-utils';

export type ReplayStep = 'setup' | 'analysis' | 'vote' | 'result';
export type ReplayEngine = 'strategy' | 'gemini';
export type Direction = 'UP' | 'DOWN';

async function requestJson<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = (await res.json().catch(() => null)) as (T & { error?: string; detail?: string }) | null;
  if (!res.ok || data === null) {
    throw new Error(data?.error || data?.detail || `Yêu cầu thất bại (mã lỗi ${res.status}).`);
  }
  return data;
}

function messageOf(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export interface ReplaySession {
  step: ReplayStep;
  setStep: (step: ReplayStep) => void;
  snapshotId: string;
  setSnapshotId: (id: string) => void;
  /** Selectable prediction time range of the current snapshot (ms), or null without a snapshot. */
  timeRange: { min: number; max: number } | null;
  timeError: string | null;
  /** Typed time: loads the candle window around it, or reports it is outside the snapshot. */
  selectTime: (ms: number) => void;
  candles: CandleDTO[];
  loadingCandles: boolean;
  engine: ReplayEngine;
  setEngine: (engine: ReplayEngine) => void;
  variant: ExternalContextVariant;
  setVariant: (variant: ExternalContextVariant) => void;
  dryRun: boolean;
  setDryRun: (value: boolean) => void;
  buyTimeMs: number;
  setBuyTimeMs: (ms: number) => void;
  buyPriceInput: string;
  setBuyPriceInput: (value: string) => void;
  hoursBefore: number;
  hasEnoughHistory: boolean;
  externalJob: ExternalAnalysisJobDTO | null;
  /** True when the current Gemini report was produced from simulated data, not a real Gemini call. */
  externalMock: boolean;
  simJob: SimulationJobResponse | null;
  busy: 'create' | 'vote' | 'reveal' | null;
  error: string | null;
  hasJob: boolean;
  userVote: Direction | null;
  hasOutcome: boolean;
  pickCandle: (candle: CandleDTO) => void;
  runAnalysis: () => Promise<void>;
  addStrategy: () => Promise<void>;
  vote: (direction: Direction) => Promise<void>;
  reveal: () => Promise<void>;
  reset: () => void;
}

export function useReplaySession(snapshots: SnapshotSummary[], initialCandles: CandleDTO[]): ReplaySession {
  const initialPick = initialCandles.length > 0 ? initialCandles[defaultPickIndex(initialCandles.length)] : null;

  const [step, setStep] = useState<ReplayStep>('setup');
  const [snapshotId, setSnapshotId] = useState(snapshots[0]?.id ?? '');
  const [candles, setCandles] = useState<CandleDTO[]>(initialCandles);
  const [loadingCandles, setLoadingCandles] = useState(false);

  const [engine, setEngine] = useState<ReplayEngine>('strategy');
  const [variant, setVariant] = useState<ExternalContextVariant>('A');
  const [dryRun, setDryRun] = useState(true);

  const [buyTimeMs, setBuyTimeMs] = useState(initialPick?.close_time_ms ?? 0);
  const [buyPriceInput, setBuyPriceInput] = useState(initialPick ? String(initialPick.close) : '');

  const [externalJob, setExternalJob] = useState<ExternalAnalysisJobDTO | null>(null);
  const [externalMock, setExternalMock] = useState(false);
  const [simJob, setSimJob] = useState<SimulationJobResponse | null>(null);
  const [busy, setBusy] = useState<'create' | 'vote' | 'reveal' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const skipFirstLoad = useRef(initialCandles.length > 0);

  const hoursBefore = useMemo(() => causalHours(candles, buyTimeMs), [candles, buyTimeMs]);
  const hasEnoughHistory = hoursBefore >= REQUIRED_HISTORY_HOURS - 0.05;

  const snapshot = useMemo(() => snapshots.find((s) => s.id === snapshotId), [snapshots, snapshotId]);
  // Last HORIZON_MINUTES of a snapshot cannot be verified against future candles.
  const timeRange = useMemo(
    () => (snapshot ? { min: snapshot.start_time_ms, max: snapshot.end_time_ms - HORIZON_MINUTES * 60_000 } : null),
    [snapshot],
  );
  const [timeError, setTimeError] = useState<string | null>(null);
  const requestRef = useRef(0);

  // Fetch a candle window: ending at the snapshot end (centerMs null) or around centerMs.
  const loadWindow = useCallback((snap: SnapshotSummary, centerMs: number | null) => {
    const request = ++requestRef.current;
    setLoadingCandles(true);
    setError(null);
    return fetch(`/api/snapshots/${snap.id}/candles?start_ms=${windowStartMs(snap, centerMs)}&limit=${WINDOW_CANDLES}`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.error || `Không tải được nến (mã lỗi ${res.status}).`);
        }
        return res.json() as Promise<CandleDTO[]>;
      })
      .then((data) => {
        if (request !== requestRef.current) return;
        setCandles(data);
        if (data.length > 0) {
          const atOrBefore = centerMs === null ? undefined : data.filter((c) => c.close_time_ms <= centerMs).pop();
          const pick = centerMs === null ? data[defaultPickIndex(data.length)] : (atOrBefore ?? data[0]);
          setBuyTimeMs(pick.close_time_ms);
          setBuyPriceInput(String(pick.close));
        }
      })
      .catch((err: unknown) => {
        if (request === requestRef.current) setError(messageOf(err, 'Không tải được nến.'));
      })
      .finally(() => {
        if (request === requestRef.current) setLoadingCandles(false);
      });
  }, []);

  // Load candles when the dataset changes.
  useEffect(() => {
    if (!snapshot) return;
    if (skipFirstLoad.current) {
      skipFirstLoad.current = false;
      return;
    }
    setTimeError(null);
    void loadWindow(snapshot, null);
    return () => {
      requestRef.current += 1;
    };
  }, [snapshot, loadWindow]);

  const selectTime = useCallback(
    (ms: number) => {
      if (!snapshot || !timeRange) return;
      if (!ms || ms < timeRange.min || ms > timeRange.max) {
        setTimeError(`Ngoài phạm vi snapshot: chọn từ ${formatDateTime(timeRange.min)} đến ${formatDateTime(timeRange.max)} (UTC+7).`);
        return;
      }
      setTimeError(null);
      void loadWindow(snapshot, ms);
    },
    [snapshot, timeRange, loadWindow],
  );

  // Poll the report while it is being written.
  const externalId = externalJob?.id;
  const externalRunning = externalJob ? isInProgress(externalJob.status) : false;
  useEffect(() => {
    if (!externalId || !externalRunning) return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/external-analysis/jobs/${externalId}`);
        if (res.ok) setExternalJob((await res.json()) as ExternalAnalysisJobDTO);
      } catch {
        // Network hiccup: try again on the next tick.
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [externalId, externalRunning]);

  const pickCandle = useCallback((candle: CandleDTO) => {
    setBuyTimeMs(candle.close_time_ms);
    setBuyPriceInput(String(candle.close));
  }, []);

  const createStrategyJob = useCallback(
    async (snapshot: string, timeMs: number, price: number) => {
      const job = await requestJson<SimulationJobResponse>('/api/replay/jobs', {
        snapshot_id: snapshot,
        buy_time_ms: timeMs,
        buy_price: price,
        horizon_minutes: HORIZON_MINUTES,
      });
      setSimJob(job);
    },
    [],
  );

  const runAnalysis = useCallback(async () => {
    setError(null);
    const price = parseFloat(buyPriceInput);
    if (Number.isNaN(price) || price <= 0) {
      setError('Nhập giá tại thời điểm lớn hơn 0.');
      return;
    }
    if (!buyTimeMs) {
      setError('Chọn thời điểm trên biểu đồ hoặc nhập thời gian.');
      return;
    }
    if (engine === 'gemini' && !hasEnoughHistory) {
      setError(`Chưa đủ ${REQUIRED_HISTORY_HOURS} giờ nến trước thời điểm dự báo. Chọn thời điểm muộn hơn hoặc tải bộ dữ liệu dài hơn.`);
      return;
    }

    setBusy('create');
    try {
      if (engine === 'gemini') {
        const job = await requestJson<ExternalAnalysisJobDTO>('/api/external-analysis/jobs', {
          snapshot_id: snapshotId,
          prediction_time_t_ms: buyTimeMs,
          purchase_price_p: price,
          horizon_minutes: HORIZON_MINUTES,
          context_variant: variant,
          mode: 'RETROSPECTIVE',
          mock_mode: dryRun,
        });
        setExternalJob(job);
        setExternalMock(dryRun);
        setSimJob(null);
        saveRecentReport({
          id: job.id,
          symbol: job.symbol,
          timeframe: job.timeframe,
          predictionTimeMs: job.prediction_time_t_ms,
          purchasePrice: job.purchase_price_p,
          savedAtMs: Date.now(),
          mock: dryRun,
        });
      } else {
        await createStrategyJob(snapshotId, buyTimeMs, price);
        setExternalJob(null);
        setExternalMock(false);
      }
      setStep('analysis');
    } catch (err) {
      setError(messageOf(err, 'Không tạo được phân tích.'));
    } finally {
      setBusy(null);
    }
  }, [buyPriceInput, buyTimeMs, engine, hasEnoughHistory, snapshotId, variant, dryRun, createStrategyJob]);

  /** Adds the entry-strategy simulation at the same point as an existing report. */
  const addStrategy = useCallback(async () => {
    if (!externalJob) return;
    setError(null);
    setBusy('create');
    try {
      await createStrategyJob(externalJob.snapshot_id, externalJob.prediction_time_t_ms, externalJob.purchase_price_p);
    } catch (err) {
      setError(messageOf(err, 'Không chạy được mô phỏng vào lệnh.'));
    } finally {
      setBusy(null);
    }
  }, [externalJob, createStrategyJob]);

  const revealAll = useCallback(async () => {
    const [ext, sim] = await Promise.all([
      externalJob ? requestJson<ExternalAnalysisJobDTO>(`/api/external-analysis/jobs/${externalJob.id}/reveal`, {}) : null,
      simJob ? requestJson<SimulationJobResponse>(`/api/replay/jobs/${simJob.job_id}/reveal`, {}) : null,
    ]);
    if (ext) setExternalJob(ext);
    if (sim) setSimJob(sim);
  }, [externalJob, simJob]);

  const reveal = useCallback(async () => {
    setError(null);
    setBusy('reveal');
    try {
      await revealAll();
    } catch (err) {
      setError(messageOf(err, 'Không mở được kết quả.'));
    } finally {
      setBusy(null);
    }
  }, [revealAll]);

  /** Locks the user's vote on every job in this session, then opens the result. */
  const vote = useCallback(
    async (direction: Direction) => {
      setError(null);
      setBusy('vote');
      try {
        const [ext, sim] = await Promise.all([
          externalJob
            ? requestJson<ExternalAnalysisJobDTO>(`/api/external-analysis/jobs/${externalJob.id}/vote`, { vote: direction })
            : null,
          simJob
            ? requestJson<SimulationJobResponse>(`/api/replay/jobs/${simJob.job_id}/vote`, { user_direction: direction })
            : null,
        ]);
        if (ext) setExternalJob(ext);
        if (sim) setSimJob(sim);
        setStep('result');
        setBusy('reveal');
        const [extRevealed, simRevealed] = await Promise.all([
          ext ? requestJson<ExternalAnalysisJobDTO>(`/api/external-analysis/jobs/${ext.id}/reveal`, {}) : null,
          sim ? requestJson<SimulationJobResponse>(`/api/replay/jobs/${sim.job_id}/reveal`, {}) : null,
        ]);
        if (extRevealed) setExternalJob(extRevealed);
        if (simRevealed) setSimJob(simRevealed);
      } catch (err) {
        setError(messageOf(err, 'Không lưu được dự đoán.'));
      } finally {
        setBusy(null);
      }
    },
    [externalJob, simJob],
  );

  const reset = useCallback(() => {
    setExternalJob(null);
    setExternalMock(false);
    setSimJob(null);
    setError(null);
    setStep('setup');
  }, []);

  const hasJob = externalJob !== null || simJob !== null;
  const userVote: Direction | null = externalJob?.user_vote ?? simJob?.user_vote?.user_direction ?? null;
  const hasOutcome =
    (externalJob !== null && externalJob.outcome !== null && externalJob.outcome !== 'PENDING') ||
    (simJob?.outcome != null && simJob.outcome.status !== 'PENDING');

  return {
    step,
    setStep,
    snapshotId,
    setSnapshotId,
    timeRange,
    timeError,
    selectTime,
    candles,
    loadingCandles,
    engine,
    setEngine,
    variant,
    setVariant,
    dryRun,
    setDryRun,
    buyTimeMs,
    setBuyTimeMs,
    buyPriceInput,
    setBuyPriceInput,
    hoursBefore,
    hasEnoughHistory,
    externalJob,
    externalMock,
    simJob,
    busy,
    error,
    hasJob,
    userVote,
    hasOutcome,
    pickCandle,
    runAnalysis,
    addStrategy,
    vote,
    reveal,
    reset,
  };
}
