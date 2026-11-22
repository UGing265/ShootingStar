import { Badge, Card } from '@/shared/ui/primitives';
import { formatHorizonMinutes, forecastDirectionLabel } from '@/shared/format';
import type { ExternalAnalysisJobDTO } from '../replay/external-types';
import { outcomeLabel } from './labels';

type Verdict = 'correct' | 'wrong' | 'flat' | 'pending' | 'unopened' | 'missing';

function verdictFor(
  prediction: string | null | undefined,
  outcome: string | null | undefined,
  unopened: boolean,
): Verdict {
  if (unopened) return 'unopened';
  if (outcome === 'FLAT' || outcome === 'UNSCORABLE') return 'flat';
  if (prediction !== 'UP' && prediction !== 'DOWN') return 'missing';
  if (outcome !== 'UP' && outcome !== 'DOWN') return 'pending';
  return prediction === outcome ? 'correct' : 'wrong';
}

function VerdictBadge({ verdict }: { verdict: Verdict }) {
  switch (verdict) {
    case 'correct':
      return <Badge variant="success">Đúng</Badge>;
    case 'wrong':
      return <Badge variant="error">Sai</Badge>;
    case 'flat':
      return <Badge variant="neutral">Không chấm</Badge>;
    case 'pending':
      return <Badge variant="neutral">Chờ kết quả</Badge>;
    case 'unopened':
      return <Badge variant="neutral">Chưa mở</Badge>;
    default:
      return <Badge variant="neutral">Không xác định</Badge>;
  }
}

export function ForecastComparison({ job }: { job: ExternalAnalysisJobDTO }) {
  const envelope = job.evidence_envelope;
  const gemini = envelope?.answer?.direction ?? job.ai_prediction?.direction ?? null;
  const alwaysUp = envelope?.baselines?.always_up ?? 'UP';
  const momentum = envelope?.baselines?.momentum_6h ?? null;
  const outcome = job.outcome;
  // The API hides the outcome until reveal. is_revealed is not part of the current DTO,
  // so a null outcome means the user has not opened the result yet.
  const revealed = (job as ExternalAnalysisJobDTO & { is_revealed?: boolean }).is_revealed;
  const unopened = outcome === null && revealed !== true;
  const threshold = envelope?.flat_threshold_pct ?? 0.5;

  const rows: Array<{ label: string; prediction: string | null; verdict: Verdict }> = [
    { label: 'Gemini', prediction: gemini, verdict: verdictFor(gemini, outcome, unopened) },
    { label: 'Luôn TĂNG', prediction: alwaysUp, verdict: verdictFor(alwaysUp, outcome, unopened) },
    { label: 'Theo đà 6h', prediction: momentum, verdict: verdictFor(momentum, outcome, unopened) },
  ];

  return (
    <Card>
      <h2 className="card-title">So sánh với luật đơn giản</h2>
      <p className="card-sub">
        Hai luật do Python tính độc lập, không nhìn câu trả lời Gemini và không tốn chi phí API.
      </p>
      <div className="table-wrap" style={{ marginTop: 12 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Nguồn dự đoán</th>
              <th>Dự đoán</th>
              <th>Kết quả</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td>
                <td>{forecastDirectionLabel(row.prediction)}</td>
                <td>
                  <VerdictBadge verdict={row.verdict} />
                </td>
              </tr>
            ))}
            <tr>
              <td>
                <strong>Thực tế sau {formatHorizonMinutes(job.horizon_minutes)}</strong>
              </td>
              <td>
                {unopened ? 'Chưa mở: khóa dự đoán của bạn để xem kết quả' : outcomeLabel(outcome)}
              </td>
              <td>
                {unopened ? (
                  <Badge variant="neutral">Chưa mở</Badge>
                ) : outcome === 'FLAT' ? (
                  <Badge variant="neutral">Không chấm</Badge>
                ) : null}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="hint" style={{ marginTop: 8 }}>
        Đi ngang khi biến động dưới {threshold}% so với giá mua; mốc đi ngang không tính đúng sai.
      </p>
    </Card>
  );
}
