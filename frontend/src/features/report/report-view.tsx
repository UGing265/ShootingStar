import { Badge, Card, Notice } from '@/shared/ui/primitives';
import {
  directionLabel,
  formatDateTimeTz,
  formatHorizonMinutes,
  formatIsoDateTime,
  formatUsd,
} from '@/shared/format';
import type { ExternalAnalysisJobDTO } from '../replay/external-types';
import { AutoRefresh } from './auto-refresh';
import { ForecastComparison } from './forecast-comparison';
import { ForecastReport } from './forecast-report';
import {
  PIPELINE_STEPS,
  externalStatusLabel,
  isInProgress,
  outcomeLabel,
  statusVariant,
} from './labels';
import { LegacyDirectionCard, LegacyReportSections } from './legacy-report-sections';
import { ScoreboardCard, type ScoreboardData } from './scoreboard-card';
import './report.css';

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="stat-label">{label}</div>
      <div className="report-meta-value">{value}</div>
    </div>
  );
}

function OutcomeVerdict({ prediction, outcome }: { prediction: string | null | undefined; outcome: string | null | undefined }) {
  if (outcome === 'FLAT') return <Badge variant="neutral">Không chấm</Badge>;
  if (outcome === 'UNSCORABLE' || !outcome) return <Badge variant="neutral">Chưa có dữ liệu</Badge>;
  if (prediction === 'ABSTAIN') return <Badge variant="neutral">Không dự báo</Badge>;
  if (prediction !== 'UP' && prediction !== 'DOWN') return <Badge variant="neutral">Chưa có dự đoán</Badge>;
  return prediction === outcome ? <Badge variant="success">Đúng</Badge> : <Badge variant="error">Sai</Badge>;
}

export function ReportView({
  job,
  live = true,
  mock = false,
  scoreboard,
  scoreboardError,
}: {
  job: ExternalAnalysisJobDTO;
  live?: boolean;
  mock?: boolean;
  scoreboard?: ScoreboardData | null;
  scoreboardError?: string | null;
}) {
  const envelope = job.evidence_envelope;
  const forecast = envelope?.protocol_version === 'forecast-6h-v1' ? envelope : null;
  const ai = job.ai_prediction;
  const inProgress = isInProgress(job.status);
  const failed = job.status === 'FAILED' || job.status === 'FAILED_INTERRUPTED';
  const hasOutcome = job.outcome !== null && job.outcome !== 'PENDING';
  const threshold = forecast?.flat_threshold_pct ?? 0.5;
  const inputLabel = forecast
    ? `${forecast.lookback_days ?? 14} ngày nến trước thời điểm dự báo`
    : '6 giờ nến trước thời điểm dự báo';

  return (
    <div className="stack">
      {live && inProgress && <AutoRefresh />}

      {mock && (
        <Notice variant="warning" title="DỮ LIỆU GIẢ LẬP (chưa gọi Gemini).">
          Báo cáo này được tạo từ dữ liệu giả để chạy thử, không phải nhận định thật của Gemini. Đừng dùng để đánh giá chất lượng dự báo.
        </Notice>
      )}

      <Card>
        <div className="spread">
          <div>
            <h2 className="card-title">
              {job.symbol} · {job.timeframe} · dự báo {formatHorizonMinutes(job.horizon_minutes)}
            </h2>
            <p className="card-sub">Tạo lúc {formatIsoDateTime(job.created_at_iso)} (UTC+7)</p>
          </div>
          <Badge variant={statusVariant(job.status)}>{externalStatusLabel(job.status)}</Badge>
        </div>
        <div className="grid-4 report-meta">
          <Meta label="Thời điểm dự báo (t)" value={formatDateTimeTz(job.prediction_time_t_ms)} />
          <Meta label="Giá tại thời điểm" value={formatUsd(job.purchase_price_p)} />
          <Meta label="Dữ liệu đầu vào" value={inputLabel} />
          <Meta label="Người xem" value={job.user_vote ? `Bạn chọn ${directionLabel(job.user_vote)}` : 'Chưa dự đoán'} />
        </div>
      </Card>

      {job.leakage_risk_banner && (
        <Notice variant="warning" title="Lưu ý:">
          Phân tích này viết sau thời điểm lịch sử nên mô hình có thể đã biết diễn biến thật. Đây là tham khảo, không phải dự báo đã kiểm chứng.
        </Notice>
      )}

      {inProgress && (
        <Card>
          <h2 className="card-title">Đang viết báo cáo</h2>
          <ol className="report-steps">
            {PIPELINE_STEPS.map((step) => (
              <li key={step.status} aria-current={job.status === step.status ? 'step' : undefined}>
                {step.label}
              </li>
            ))}
          </ol>
        </Card>
      )}

      {failed && (
        <Notice variant="error" title={`${externalStatusLabel(job.status)}.`}>
          {job.error_message || 'Không có thông tin lỗi.'}
        </Notice>
      )}
      {job.status === 'RESEARCH_INCOMPLETE' && (
        <Notice variant="warning" title="Tra cứu chưa đầy đủ.">
          {job.error_message || 'Không truy xuất được đủ tài liệu độc lập.'}
        </Notice>
      )}
      {job.status === 'INSUFFICIENT_HISTORY' && (
        <Notice variant="neutral" title="Thiếu lịch sử nến.">
          Cần ít nhất 14 ngày nến liên tục trước thời điểm dự báo cho mô hình 6 giờ.
        </Notice>
      )}

      {forecast?.answer ? <ForecastReport job={job} /> : <LegacyDirectionCard job={job} />}

      {hasOutcome && (
        <Card>
          <h2 className="card-title">Kết quả thực tế</h2>
          <div className="grid-4 report-meta">
            <Meta label="Thị trường" value={outcomeLabel(job.outcome)} />
            <Meta label={`Giá sau ${formatHorizonMinutes(job.horizon_minutes)}`} value={formatUsd(job.target_price)} />
            <div>
              <div className="stat-label">Gemini</div>
              <div className="report-meta-value">
                <OutcomeVerdict
                  prediction={forecast?.answer?.direction ?? ai?.direction}
                  outcome={job.outcome}
                />
              </div>
            </div>
            <div>
              <div className="stat-label">Bạn</div>
              <div className="report-meta-value">
                <OutcomeVerdict prediction={job.user_vote} outcome={job.outcome} />
              </div>
            </div>
          </div>
          {job.outcome === 'FLAT' && (
            <p style={{ marginTop: 12 }}>Đi ngang (dưới {threshold}%), không chấm điểm.</p>
          )}
        </Card>
      )}

      {forecast?.answer && <ForecastComparison job={job} />}
      {scoreboard !== undefined && <ScoreboardCard data={scoreboard} error={scoreboardError} />}
      {!forecast && <LegacyReportSections job={job} />}

      {(ai || forecast) && (
        <details className="report-details report-tech">
          <summary>Chi tiết kỹ thuật</summary>
          <p className="hint">
            Mô hình: {ai?.model_id ?? 'Chưa có dữ liệu'} · Phiên bản lời nhắc:{' '}
            {ai?.prompt_version ?? forecast?.prompt_version ?? 'Chưa có dữ liệu'}
            {forecast?.lookback_days ? ` · Nhìn lại ${forecast.lookback_days} ngày` : ''}
          </p>
        </details>
      )}
    </div>
  );
}
