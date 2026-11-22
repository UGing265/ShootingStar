'use client';

import React from 'react';
import type { CandleDTO, SnapshotSummary } from '../data/types';
import { Notice } from '@/shared/ui/primitives';
import { ReplayAnalysis } from './replay-analysis';
import { ReplayResult } from './replay-result';
import { ReplaySetup } from './replay-setup';
import { ReplayVote } from './replay-vote';
import { useReplaySession, type ReplayStep } from './use-replay-session';
import './replay.css';

interface ReplayPlayerProps {
  snapshots: SnapshotSummary[];
  initialCandles: CandleDTO[];
}

const STEPS: ReadonlyArray<{ id: ReplayStep; label: string }> = [
  { id: 'setup', label: 'Chọn thời điểm' },
  { id: 'analysis', label: 'Phân tích' },
  { id: 'vote', label: 'Dự đoán của bạn' },
  { id: 'result', label: 'Kết quả' },
];

export function ReplayPlayer({ snapshots, initialCandles }: ReplayPlayerProps) {
  const session = useReplaySession(snapshots, initialCandles);
  const { step, error } = session;
  const timeframe = snapshots.find((s) => s.id === session.snapshotId)?.timeframe ?? '1m';
  const currentIndex = STEPS.findIndex((s) => s.id === step);

  return (
    <div className="stack">
      <ol className="replay-steps" aria-label="Các bước mô phỏng">
        {STEPS.map((s, i) => (
          <li
            key={s.id}
            aria-current={s.id === step ? 'step' : undefined}
            data-done={i < currentIndex}
          >
            <span className="replay-step-num">{i + 1}</span>
            {s.label}
          </li>
        ))}
      </ol>

      {error && step === 'setup' && <Notice variant="error">{error}</Notice>}

      {step === 'setup' && <ReplaySetup session={session} snapshots={snapshots} />}
      {step === 'analysis' && session.hasJob && <ReplayAnalysis session={session} timeframe={timeframe} />}
      {step === 'vote' && session.hasJob && <ReplayVote session={session} />}
      {step === 'result' && session.hasJob && <ReplayResult session={session} timeframe={timeframe} />}
    </div>
  );
}
