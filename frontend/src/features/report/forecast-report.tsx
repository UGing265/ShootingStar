import { Card, Notice } from '@/shared/ui/primitives';
import { formatHorizonMinutes, formatUsd, forecastDirectionLabel } from '@/shared/format';
import type { ExternalAnalysisJobDTO } from '../replay/external-types';
import { forecastCitations, replaceForecastFeatureIds } from './report-format';
import { confidenceLabel, verificationIssueLabel } from './labels';

export function ForecastReport({ job }: { job: ExternalAnalysisJobDTO }) {
  const envelope = job.evidence_envelope;
  const answer = envelope?.answer;
  if (!answer) return null;

  const features = envelope?.digest?.features ?? [];
  const reasons = answer.reasons ?? [];
  const risks = answer.risks ?? [];
  const agreement = envelope?.agreement_score;
  const aligned = answer.direction === 'UP' ? agreement?.up : agreement?.down;
  const verification = envelope?.verification;
  const verificationIssues = verification?.issues ?? [];
  const thresholdNote = envelope?.possible_memorization === true;

  return (
    <div className="stack">
      <Card>
        <div className="spread">
          <h2 className="card-title">Nhận định hướng giá</h2>
          <span className={`report-pill report-pill-${answer.direction === 'UP' ? 'up' : 'down'}`}>
            {forecastDirectionLabel(answer.direction)}
          </span>
        </div>
        <p style={{ marginTop: 12 }}>
          Sau {formatHorizonMinutes(job.horizon_minutes)}, giá có thể{' '}
          <strong>{answer.direction === 'UP' ? 'cao hơn' : 'thấp hơn'}</strong> mức mua{' '}
          {formatUsd(job.purchase_price_p)}.
        </p>

        <div className="grid-2" style={{ marginTop: 12 }}>
          <div>
            <div className="stat-label">Độ tin cậy</div>
            <div className="report-meta-value">{confidenceLabel(answer.confidence)}</div>
            <div className="hint">model tự đánh giá, chưa kiểm chứng</div>
          </div>
          <div>
            <div className="stat-label">Điểm đồng thuận</div>
            <div className="report-meta-value">
              {agreement ? `${aligned ?? 0}/${agreement.total} chỉ số cùng chiều` : 'Chưa có dữ liệu'}
            </div>
          </div>
        </div>

        <div className="stack-sm" style={{ marginTop: 12 }}>
          <span className="label">Lý do</span>
          {reasons.map((reason, index) => {
            const citations = forecastCitations(reason.feature_ids, features);
            return (
              <div key={index} className="card-flat">
                <p className="report-prose" style={{ marginTop: 0 }}>
                  {replaceForecastFeatureIds(reason.text, features)}
                </p>
                {citations.length > 0 && (
                  <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                    {citations.map((citation, citationIndex) => (
                      <span key={`${citation.label}-${citationIndex}`} className="report-chip">
                        {citation.label}: <strong>{citation.value}</strong>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {risks.length > 0 && (
          <div className="stack-sm" style={{ marginTop: 12 }}>
            <span className="label">Rủi ro</span>
            <ul className="report-list">
              {risks.map((risk, index) => (
                <li key={index}>{risk}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {thresholdNote && (
        <Notice variant="warning" title="Có thể mô hình đã biết trước diễn biến.">
          Mốc này nằm trước mốc kiến thức của mô hình (01/2025), nên kết quả có thể bị nhớ sẵn thay vì suy
          luận. Thống kê được tách riêng.
        </Notice>
      )}

      {verification && verification.valid === false && (
        <Notice variant="warning" title="Cảnh báo kiểm chứng.">
          <p>
            Có {verificationIssues.length} điểm chưa khớp giữa lời mô hình và dữ liệu. Đọc kết quả với mức
            tin cậy thấp hơn.
          </p>
          <ul className="report-list">
            {verificationIssues.slice(0, 6).map((issue, index) => (
              <li key={index}>
                Lý do {issue.reason_index + 1}: {verificationIssueLabel(issue.type)}
                {issue.type === 'unmatched_number' ? ` (${issue.value})` : ''}.
              </li>
            ))}
          </ul>
        </Notice>
      )}
    </div>
  );
}
