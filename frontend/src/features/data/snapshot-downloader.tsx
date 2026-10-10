'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { IngestionJobDTO, PreviewIngestionDTO } from './types';
// Helper to format ISO date string for datetime-local (UTC+7)
function toUtc7InputString(date: Date): string {
  const utcMs = date.getTime();
  const utc7Ms = utcMs + 7 * 60 * 60 * 1000;
  const d = new Date(utc7Ms);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

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
  const [isOpen, setIsOpen] = useState(false);

  // Form states (default to last 7 days)
  const [symbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState<'1m' | '5m'>('1m');

  const defaultEnd = new Date();
  const defaultStart = new Date(defaultEnd.getTime() - 7 * 24 * 60 * 60 * 1000);

  const [startDateStr, setStartDateStr] = useState(() => toUtc7InputString(defaultStart));
  const [endDateStr, setEndDateStr] = useState(() => toUtc7InputString(defaultEnd));

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
        setFormError(data.error || data.detail || 'Không thể tạo tác vụ tải snapshot.');
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

  return (
    <div style={{ marginBottom: 20 }}>
      {/* Trigger Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
          padding: '14px 18px',
          background: 'var(--surface-primary, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: 8,
        }}
      >
        <div>
          <span style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary, #0f172a)' }}>
            📥 Nạp / Tải dữ liệu Snapshot
          </span>
          <p style={{ margin: '4px 0 0 0', fontSize: 13, color: 'var(--text-secondary, #64748b)' }}>
            Tải nến từ Binance Spot, xác thực dữ liệu và tạo bản chụp Parquet mới kèm mã kiểm tra SHA-256.
          </p>
        </div>

        <button
          onClick={() => setIsOpen(!isOpen)}
          className="button"
          style={{
            padding: '8px 16px',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            backgroundColor: isOpen ? '#f1f5f9' : '#2563eb',
            color: isOpen ? '#0f172a' : '#ffffff',
            border: isOpen ? '1px solid #cbd5e1' : 'none',
            borderRadius: 6,
          }}
        >
          {isOpen ? '✕ Đóng bảng tải' : '⚡ Tải Snapshot mới từ Binance'}
        </button>
      </div>

      {/* Downloader Form & Live Progress Panel */}
      {isOpen && (
        <div
          style={{
            marginTop: 10,
            padding: '20px 24px',
            background: 'var(--surface-primary, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: 8,
            boxShadow: 'none',
          }}
        >
          <form onSubmit={handlePreview}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
              {/* Symbol */}
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary, #64748b)', marginBottom: 6 }}>
                  CẶP GIAO DỊCH
                </label>
                <input
                  type="text"
                  value={symbol}
                  disabled
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    fontSize: 13,
                    borderRadius: 6,
                    border: '1px solid #e2e8f0',
                    background: '#f8fafc',
                    color: '#334155',
                    fontWeight: 500,
                  }}
                />
              </div>

              {/* Timeframe */}
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary, #64748b)', marginBottom: 6 }}>
                  KHUNG NẾN
                </label>
                <div style={{ display: 'flex', gap: 10 }}>
                  {(['1m', '5m'] as const).map((tf) => (
                    <button
                      type="button"
                      key={tf}
                      onClick={() => {
                        setTimeframe(tf);
                        setPreviewData(null);
                        setFormError(null);
                      }}
                      style={{
                        flex: 1,
                        padding: '8px 0',
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: 'pointer',
                        borderRadius: 6,
                        border: timeframe === tf ? '2px solid #2563eb' : '1px solid #cbd5e1',
                        background: timeframe === tf ? '#eff6ff' : '#ffffff',
                        color: timeframe === tf ? '#1d4ed8' : '#475569',
                      }}
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              </div>

              {/* Start Date */}
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary, #64748b)', marginBottom: 6 }}>
                  TỪ NGÀY (UTC+7)
                </label>
                <input
                  type="datetime-local"
                  step="60"
                  value={startDateStr}
                  onChange={(e) => {
                    setStartDateStr(e.target.value);
                    setPreviewData(null);
                    setFormError(null);
                  }}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    fontSize: 13,
                    borderRadius: 6,
                    border: '1px solid #cbd5e1',
                    background: '#ffffff',
                  }}
                />
              </div>

              {/* End Date */}
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary, #64748b)', marginBottom: 6 }}>
                  ĐẾN NGÀY (UTC+7)
                </label>
                <input
                  type="datetime-local"
                  step="60"
                  value={endDateStr}
                  onChange={(e) => {
                    setEndDateStr(e.target.value);
                    setPreviewData(null);
                    setFormError(null);
                  }}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    fontSize: 13,
                    borderRadius: 6,
                    border: '1px solid #cbd5e1',
                    background: '#ffffff',
                  }}
                />
            </div>
          </div>

            <div
              style={{
                marginTop: 16,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 12,
              }}
            >
              <span style={{ fontSize: 12, color: 'var(--text-secondary, #64748b)' }}>
                ℹ️ Lưu ý: Tối đa 65 ngày một lần tải. Nến chưa đóng sẽ tự động bị loại bỏ để đảm bảo tính nhân quả.
              </span>

              <button
                type="submit"
                disabled={isPreviewing || isSubmitting || (activeJob?.status === 'RUNNING')}
                style={{
                  padding: '9px 20px',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: isPreviewing || isSubmitting || activeJob?.status === 'RUNNING' ? 'not-allowed' : 'pointer',
                  backgroundColor: isPreviewing || isSubmitting || activeJob?.status === 'RUNNING' ? '#94a3b8' : '#2563eb',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: 6,
                }}
              >
                {isPreviewing ? '⏳ Đang kiểm tra Binance...' : '👁️ Xem trước (Preview dữ liệu)'}
              </button>
            </div>
          </form>

          {/* Preview Inspection Box */}
          {previewData && (
            <div
              style={{
                marginTop: 20,
                padding: '16px',
                borderRadius: 8,
                background: '#f8fafc',
                border: '1px solid #cbd5e1',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                <div>
                  <span style={{ fontWeight: 600, fontSize: 14, color: '#0f172a' }}>
                    👁️ Kết quả Xem trước (Preview)
                  </span>
                  <span style={{ marginLeft: 10, fontSize: 12, padding: '2px 8px', borderRadius: 4, background: '#e2e8f0', color: '#475569' }}>
                    Nguồn: {previewData.data_source}
                  </span>
                </div>
                <span style={{ fontSize: 12, color: '#64748b' }}>
                  Token: {previewData.preview_token}
                </span>
              </div>

              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
                <div style={{ background: '#ffffff', padding: '10px', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                  <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>SỐ NẾN DỰ KIẾN</span>
                  <strong style={{ fontSize: 14 }}>~{previewData.estimated_candle_count.toLocaleString()} nến</strong>
                </div>
                <div style={{ background: '#ffffff', padding: '10px', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                  <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>NẾN MẪU ĐÃ LẤY</span>
                  <strong style={{ fontSize: 14 }}>{previewData.sampled_candles_count} nến</strong>
                </div>
                <div style={{ background: '#ffffff', padding: '10px', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                  <span style={{ fontSize: 11, color: '#64748b', display: 'block' }}>CHẤT LƯỢNG MẪU</span>
                  <strong style={{ fontSize: 14, color: previewData.quality_status === 'OK' ? '#16a34a' : '#ea580c' }}>
                    {previewData.quality_status === 'OK' ? '✓ Đạt chuẩn (OK)' : previewData.quality_status}
                  </strong>
                </div>
              </div>

              {previewData.sample_candles.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#475569', display: 'block', marginBottom: 6 }}>
                    Mẫu 5 nến đầu tiên nhận được từ API:
                  </span>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse', background: '#ffffff' }}>
                      <thead>
                        <tr style={{ background: '#f1f5f9', textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
                          <th style={{ padding: '6px 8px' }}>Mở nến (UTC+7)</th>
                          <th style={{ padding: '6px 8px' }}>Mở</th>
                          <th style={{ padding: '6px 8px' }}>Cao</th>
                          <th style={{ padding: '6px 8px' }}>Thấp</th>
                          <th style={{ padding: '6px 8px' }}>Đóng</th>
                          <th style={{ padding: '6px 8px' }}>Khối lượng</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.sample_candles.slice(0, 5).map((c, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>
                              {new Date(c.open_time_ms + 7 * 3600000).toISOString().replace('T', ' ').slice(0, 19)}
                            </td>
                            <td style={{ padding: '6px 8px' }}>{c.open.toLocaleString()}</td>
                            <td style={{ padding: '6px 8px' }}>{c.high.toLocaleString()}</td>
                            <td style={{ padding: '6px 8px' }}>{c.low.toLocaleString()}</td>
                            <td style={{ padding: '6px 8px', fontWeight: 600 }}>{c.close.toLocaleString()}</td>
                            <td style={{ padding: '6px 8px' }}>{c.volume.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div
                style={{
                  marginTop: 16,
                  padding: '12px',
                  borderRadius: 6,
                  background: '#fef3c7',
                  border: '1px solid #fde68a',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: 10,
                }}
              >
                <span style={{ fontSize: 12, color: '#92400e' }}>
                  ⚠️ Bản xem trước <strong>chưa được lưu vào Database</strong> và chưa tạo Snapshot chính thức. Bấm nút bên dưới để xác nhận nạp.
                </span>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => setPreviewData(null)}
                    style={{
                      padding: '7px 14px',
                      fontSize: 12,
                      fontWeight: 500,
                      cursor: 'pointer',
                      background: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: 6,
                    }}
                  >
                    ✕ Hủy
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirmIngestion}
                    disabled={isSubmitting || activeJob?.status === 'RUNNING'}
                    style={{
                      padding: '7px 16px',
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: isSubmitting || activeJob?.status === 'RUNNING' ? 'not-allowed' : 'pointer',
                      background: '#16a34a',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: 6,
                    }}
                  >
                    {isSubmitting ? 'Đang gửi...' : '📥 Xác nhận Nạp chính thức vào DB'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Form Error */}
          {formError && (
            <div
              style={{
                marginTop: 14,
                padding: '10px 14px',
                borderRadius: 6,
                background: '#fef2f2',
                border: '1px solid #fecaca',
                color: '#dc2626',
                fontSize: 13,
              }}
            >
              ⚠️ {formError}
            </div>
          )}

          {/* Active Job Status Tracker */}
          {activeJob && (
            <div
              style={{
                marginTop: 20,
                padding: '16px',
                borderRadius: 6,
                background:
                  activeJob.status === 'COMPLETED'
                    ? '#f0fdf4'
                    : activeJob.status === 'FAILED'
                    ? '#fef2f2'
                    : '#f8fafc',
                border: `1px solid ${
                  activeJob.status === 'COMPLETED'
                    ? '#bbf7d0'
                    : activeJob.status === 'FAILED'
                    ? '#fecaca'
                    : '#e2e8f0'
                }`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                <div>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '3px 8px',
                      borderRadius: 4,
                      fontSize: 12,
                      fontWeight: 600,
                      backgroundColor:
                        activeJob.status === 'COMPLETED'
                          ? '#dcfce7'
                          : activeJob.status === 'FAILED'
                          ? '#fee2e2'
                          : '#e0f2fe',
                      color:
                        activeJob.status === 'COMPLETED'
                          ? '#16a34a'
                          : activeJob.status === 'FAILED'
                          ? '#dc2626'
                          : '#0284c7',
                    }}
                  >
                    {activeJob.status === 'RUNNING' && '⏳ ĐANG TẢI DỮ LIỆU TỪ BINANCE...'}
                    {activeJob.status === 'COMPLETED' && '✓ TẢI SNAPSHOT THÀNH CÔNG'}
                    {activeJob.status === 'FAILED' && '✕ TẢI THẤT BẠI'}
                    {activeJob.status === 'PENDING' && 'ĐANG CHỜ TIẾN TRÌNH...'}
                  </span>
                  <span style={{ marginLeft: 10, fontSize: 12, color: '#64748b' }}>
                    Job ID: {activeJob.job_id.slice(0, 8)}...
                  </span>
                </div>

                {activeJob.status === 'COMPLETED' && activeJob.snapshot_id && (
                  <button
                    onClick={() => handleViewNewSnapshot(activeJob.snapshot_id!)}
                    style={{
                      padding: '6px 14px',
                      fontSize: 13,
                      fontWeight: 600,
                      backgroundColor: '#16a34a',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: 6,
                      cursor: 'pointer',
                    }}
                  >
                    👁️ Mở Snapshot này trên biểu đồ ngay
                  </button>
                )}
              </div>

              {activeJob.status === 'RUNNING' && (
                <div style={{ marginTop: 10, fontSize: 13, color: '#334155' }}>
                  Hệ thống đang kết nối Binance Spot API, phân trang nến 1000 hàng/lần, kiểm tra khoảng trống và tính SHA-256. Vui lòng chờ vài giây...
                </div>
              )}

              {activeJob.status === 'COMPLETED' && (
                <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, fontSize: 13 }}>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>SỐ NẾN HỢP LỆ</span>
                    <strong>{activeJob.valid_candles_count?.toLocaleString()} nến</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>ĐỘ BAO PHỦ</span>
                    <strong>{activeJob.coverage_ratio !== null ? (activeJob.coverage_ratio * 100).toFixed(2) + '%' : 'N/A'}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>CHUỖI NGUYÊN BẢN</span>
                    <strong>{activeJob.is_pristine ? 'Có (Pristine)' : 'Không (Có khoảng trống)'}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>MÃ SNAPSHOT SHA-256</span>
                    <strong style={{ fontFamily: 'var(--font-mono)' }}>{activeJob.snapshot_id?.slice(0, 16)}...</strong>
                  </div>
                </div>
              )}

              {activeJob.status === 'FAILED' && (
                <div style={{ marginTop: 10, fontSize: 13, color: '#dc2626' }}>
                  Lỗi: {activeJob.error_message || 'Không rõ nguyên nhân lỗi.'}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
