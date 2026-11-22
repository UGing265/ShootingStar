'use client';

import React, { useState, useEffect, useRef, useId } from 'react';
import { useRouter } from 'next/navigation';
import { Card, Badge, StatBox, Notice } from '@/shared/ui/primitives';
import { formatDateTime, formatInt, formatUsd } from '@/shared/format';
import { formatCoverage } from './components';
import { IngestionJobDTO, PreviewIngestionDTO } from './types';

// Convert UTC+7 datetime-local string to UTC epoch ms
function utc7InputToEpochMs(val: string): number {
  const [datePart, timePart] = val.split('T');
  if (!datePart || !timePart) return NaN;
  const [yyyy, mm, dd] = datePart.split('-').map(Number);
  const [hh, min] = timePart.split(':').map(Number);
  return Date.UTC(yyyy, mm - 1, dd, hh - 7, min, 0, 0);
}
type IntervalHandle = number;

export function SnapshotDownloader() {
  const router = useRouter();
  const uid = useId();
  const [isOpen, setIsOpen] = useState(false);

  // Form states (default to last 7 days)
  const [symbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState<'1m' | '5m'>('1m');

  const defaultEnd = new Date();
  const defaultStart = new Date(defaultEnd.getTime() - 7 * 24 * 60 * 60 * 1000);

  // datetime-local values are UTC+7
  const [startDateStr, setStartDateStr] = useState(() => formatDateTime(defaultStart.getTime()).replace(' ', 'T'));
  const [endDateStr, setEndDateStr] = useState(() => formatDateTime(defaultEnd.getTime()).replace(' ', 'T'));

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [previewData, setPreviewData] = useState<PreviewIngestionDTO | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  // Active job polling state
  const [activeJob, setActiveJob] = useState<IngestionJobDTO | null>(null);
  const pollTimerRef = useRef<IntervalHandle | undefined>(undefined);

  // Stop polling on unmount
  useEffect(() => {
    return () => {
      window.clearInterval(pollTimerRef.current);
    };
  }, []);

  // Poll active job
  const startPolling = (jobId: string) => {
    window.clearInterval(pollTimerRef.current);

    pollTimerRef.current = window.setInterval(async () => {
      try {
        const res = await fetch(`/api/ingestion/jobs/${jobId}`);
        if (!res.ok) return;
        const job: IngestionJobDTO = await res.json();
        setActiveJob(job);

        if (job.status === 'COMPLETED' || job.status === 'FAILED') {
          window.clearInterval(pollTimerRef.current);
          pollTimerRef.current = undefined;
        }
      } catch {
        // network retry next tick
      }
    }, 1500);
  };
  const handlePreview = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setPreviewData(null);

    const startMs = utc7InputToEpochMs(startDateStr);
    const endMs = utc7InputToEpochMs(endDateStr);

    if (isNaN(startMs) || isNaN(endMs)) {
      setFormError('Định dạng thời gian không hợp lệ.');
      return;
    }

    if (startMs >= endMs) {
      setFormError('Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc.');
      return;
    }

    const nowMs = Date.now();
    if (startMs > nowMs) {
      setFormError('Thời gian bắt đầu không được ở trong tương lai.');
      return;
    }

    const maxSpanMs = 65 * 24 * 60 * 60 * 1000;
    if (endMs - startMs > maxSpanMs) {
      setFormError('Khoảng thời gian nạp tối đa là 65 ngày mỗi lần.');
      return;
    }

    setIsPreviewing(true);
    try {
      const res = await fetch('/api/ingestion/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          timeframe,
          start_time_ms: startMs,
          end_time_ms: endMs,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setFormError(data.error || data.detail || 'Không thể xem trước dữ liệu.');
        return;
      }

      setPreviewData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Lỗi kết nối khi xem trước.';
      setFormError(msg);
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleConfirmIngestion = async () => {
    if (!previewData) return;
    setFormError(null);
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/ingestion/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: previewData.symbol,
          timeframe: previewData.timeframe,
          start_time_ms: previewData.start_time_ms,
          end_time_ms: previewData.end_time_ms,
          preview_token: previewData.preview_token,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setFormError(data.error || data.detail || 'Không thể tạo tác vụ tải dữ liệu.');
        setIsSubmitting(false);
        return;
      }

      setActiveJob(data);
      startPolling(data.job_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Lỗi kết nối máy chủ.';
      setFormError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleViewNewSnapshot = (snapId: string) => {
    router.push(`/data?snapshot_id=${snapId}`);
    router.refresh();
  };

  const isBusy = isPreviewing || isSubmitting || activeJob?.status === 'RUNNING';
  const panelId = `${uid}-panel`;
  const resetPreview = () => {
    setPreviewData(null);
    setFormError(null);
  };

  const jobVariant =
    activeJob?.status === 'COMPLETED' ? 'success' : activeJob?.status === 'FAILED' ? 'error' : 'neutral';
  const jobLabel: Record<IngestionJobDTO['status'], string> = {
    PENDING: 'Đang chờ xử lý',
    RUNNING: 'Đang tải dữ liệu từ Binance',
    COMPLETED: 'Tải dữ liệu thành công',
    FAILED: 'Tải dữ liệu thất bại',
  };

  return (
    <Card compact>
      <div className="stack">
        <div className="data-ingest-actions">
          <div>
            <h2 className="card-title">Tải thêm dữ liệu giá</h2>
            <p className="card-sub data-ingest-hint">
              Lấy nến lịch sử từ Binance Spot, kiểm tra khoảng thiếu rồi lưu thành bộ dữ liệu mới.
            </p>
          </div>
          <button
            type="button"
            className={isOpen ? 'btn btn-quiet btn-sm' : 'btn btn-sm'}
            aria-expanded={isOpen}
            aria-controls={panelId}
            onClick={() => setIsOpen(!isOpen)}
          >
            {isOpen ? 'Đóng' : 'Tải bộ dữ liệu mới'}
          </button>
        </div>

        {isOpen && (
          <div id={panelId} className="stack">
            <form onSubmit={handlePreview} className="stack">
              <div className="grid-4">
                <div className="field">
                  <label className="label" htmlFor={`${uid}-symbol`}>Cặp giao dịch</label>
                  <input id={`${uid}-symbol`} type="text" className="input" value={symbol} disabled readOnly />
                </div>

                <div className="field">
                  <span className="label" id={`${uid}-tf`}>Khung nến</span>
                  <div className="seg" role="group" aria-labelledby={`${uid}-tf`}>
                    {(['1m', '5m'] as const).map((tf) => (
                      <button
                        type="button"
                        key={tf}
                        className="seg-btn"
                        aria-pressed={timeframe === tf}
                        onClick={() => {
                          setTimeframe(tf);
                          resetPreview();
                        }}
                      >
                        {tf}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="field">
                  <label className="label" htmlFor={`${uid}-start`}>Từ (UTC+7)</label>
                  <input
                    id={`${uid}-start`}
                    type="datetime-local"
                    step="60"
                    className="input"
                    value={startDateStr}
                    onChange={(e) => {
                      setStartDateStr(e.target.value);
                      resetPreview();
                    }}
                  />
                </div>

                <div className="field">
                  <label className="label" htmlFor={`${uid}-end`}>Đến (UTC+7)</label>
                  <input
                    id={`${uid}-end`}
                    type="datetime-local"
                    step="60"
                    className="input"
                    value={endDateStr}
                    onChange={(e) => {
                      setEndDateStr(e.target.value);
                      resetPreview();
                    }}
                  />
                </div>
              </div>

              <div className="data-ingest-actions">
                <span className="hint">
                  Tối đa 65 ngày mỗi lần. Nến chưa đóng sẽ bị loại để dữ liệu không nhìn trước tương lai.
                </span>
                <button type="submit" className="btn btn-sm" disabled={isBusy}>
                  {isPreviewing ? 'Đang kiểm tra Binance...' : 'Xem trước'}
                </button>
              </div>
            </form>

            {formError && <Notice variant="error">{formError}</Notice>}

            {previewData && (
              <div className="card-flat data-preview">
                <div className="spread">
                  <strong>Kết quả xem trước</strong>
                  <Badge variant="neutral">Nguồn: {previewData.data_source}</Badge>
                </div>

                <div className="data-preview-stats">
                  <StatBox label="Số nến dự kiến" value={`~${formatInt(previewData.estimated_candle_count)}`} />
                  <StatBox label="Nến mẫu đã lấy" value={formatInt(previewData.sampled_candles_count)} />
                  <div>
                    <div className="stat-label">Chất lượng mẫu</div>
                    <div className="stat-value">
                      <Badge variant={previewData.quality_status === 'OK' ? 'success' : 'warning'}>
                        {previewData.quality_status === 'OK' ? 'Đạt chuẩn' : previewData.quality_status}
                      </Badge>
                    </div>
                  </div>
                </div>

                {previewData.sample_candles.length > 0 && (
                  <div className="stack-sm">
                    <span className="label">5 nến đầu tiên nhận được</span>
                    <div className="table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Mở nến (UTC+7)</th>
                            <th>Mở</th>
                            <th>Cao</th>
                            <th>Thấp</th>
                            <th>Đóng</th>
                            <th>Khối lượng</th>
                          </tr>
                        </thead>
                        <tbody>
                          {previewData.sample_candles.slice(0, 5).map((c) => (
                            <tr key={c.open_time_ms}>
                              <td>{formatDateTime(c.open_time_ms)}</td>
                              <td>{formatUsd(c.open)}</td>
                              <td>{formatUsd(c.high)}</td>
                              <td>{formatUsd(c.low)}</td>
                              <td><strong>{formatUsd(c.close)}</strong></td>
                              <td>{c.volume.toFixed(2)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                <Notice
                  variant="warning"
                  action={
                    <div className="row">
                      <button type="button" className="btn btn-quiet btn-sm" onClick={() => setPreviewData(null)}>
                        Hủy
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={handleConfirmIngestion}
                        disabled={isSubmitting || activeJob?.status === 'RUNNING'}
                      >
                        {isSubmitting ? 'Đang gửi...' : 'Xác nhận tải về'}
                      </button>
                    </div>
                  }
                >
                  Đây mới là bản xem trước, <strong>chưa được lưu</strong>. Bấm “Xác nhận tải về” để tạo bộ dữ liệu.
                </Notice>
              </div>
            )}

            {activeJob && (
              <Notice
                variant={jobVariant}
                action={
                  activeJob.status === 'COMPLETED' && activeJob.snapshot_id ? (
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => handleViewNewSnapshot(activeJob.snapshot_id!)}
                    >
                      Xem trên biểu đồ
                    </button>
                  ) : undefined
                }
              >
                <div className="stack-sm">
                  <div className="row">
                    {activeJob.status === 'RUNNING' && <span className="spinner" aria-hidden="true" />}
                    <strong>{jobLabel[activeJob.status]}</strong>
                    <span className="muted">Mã tác vụ: {activeJob.job_id.slice(0, 8)}</span>
                  </div>

                  {activeJob.status === 'RUNNING' && (
                    <span>Đang lấy nến từ Binance Spot (1000 nến mỗi lượt) và kiểm tra khoảng thiếu. Vui lòng chờ vài giây.</span>
                  )}

                  {activeJob.status === 'COMPLETED' && (
                    <div className="data-job-stats">
                      <StatBox label="Số nến hợp lệ" value={formatInt(activeJob.valid_candles_count)} />
                      <StatBox label="Độ bao phủ" value={formatCoverage(activeJob.coverage_ratio)} />
                      <StatBox
                        label="Chất lượng"
                        value={
                          activeJob.is_pristine === null
                            ? 'Chưa có dữ liệu'
                            : activeJob.is_pristine
                              ? 'Không thiếu khoảng'
                              : 'Có khoảng thiếu'
                        }
                      />
                      <StatBox
                        label="Mã bộ dữ liệu"
                        value={activeJob.snapshot_id ? activeJob.snapshot_id.slice(0, 8) : 'Chưa có dữ liệu'}
                      />
                    </div>
                  )}

                  {activeJob.status === 'FAILED' && (
                    <span>Lỗi: {activeJob.error_message || 'Không rõ nguyên nhân.'}</span>
                  )}
                </div>
              </Notice>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
