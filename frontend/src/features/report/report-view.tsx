import ReactMarkdown from 'react-markdown';
import { Badge, Card, Notice } from '@/shared/ui/primitives';
import { directionArrow, directionLabel, formatDateTime, formatDateTimeTz, formatIsoDateTime, formatUsd } from '@/shared/format';
import type {
  ExternalAnalysisJobDTO,
  PatternDiagnostic,
  ReportSections,
  ResearchSourceItem,
} from '../replay/external-types';
import { cleanSectionContent, formatCanonicalFeatureTable } from './report-format';
import {
  PIPELINE_STEPS,
  criterionLabel,
  externalStatusLabel,
  isInProgress,
  matchLabel,
  outcomeLabel,
  statusVariant,
} from './labels';
import { AutoRefresh } from './auto-refresh';
import './report.css';

const SECTION_DEFS: ReadonlyArray<{ key: keyof ReportSections; title: string }> = [
  { key: 'cau_hoi_va_du_lieu', title: 'Câu hỏi và dữ liệu' },
  { key: 'dien_bien_quan_sat', title: 'Diễn biến quan sát' },
  { key: 'gia_thuyet_va_mau_duoc_kiem', title: 'Giả thuyết và mẫu được kiểm tra' },
  { key: 'tai_lieu_da_tra', title: 'Tài liệu đã tra cứu' },
  { key: 'lap_luan_va_phan_bien', title: 'Lập luận và phản biện' },
  { key: 'ket_luan_co_dieu_kien', title: 'Kết luận có điều kiện' },
  { key: 'gioi_han_va_kha_nang_ap_dung', title: 'Giới hạn và khả năng áp dụng' },
];

function DirectionPill({ direction }: { direction: string | null | undefined }) {
  const tone = direction === 'UP' ? 'up' : direction === 'DOWN' ? 'down' : 'neutral';
  return (
    <span className={`report-pill report-pill-${tone}`}>
      {directionArrow(direction)} {directionLabel(direction)}
    </span>
  );
}

function Verdict({ correct, abstained }: { correct: boolean; abstained?: boolean }) {
  if (abstained) return <Badge variant="neutral">Không dự báo</Badge>;
  return correct ? <Badge variant="success">Đúng</Badge> : <Badge variant="error">Sai</Badge>;
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="stat-label">{label}</div>
      <div className="report-meta-value">{value}</div>
    </div>
  );
}

function PatternChecks({ diagnostics }: { diagnostics: PatternDiagnostic[] }) {
  return (
    <Card>
      <h2 className="card-title">Đối chiếu mẫu nến</h2>
      <p className="card-sub">Kiểm tra bằng quy tắc cố định, chỉ dùng nến đã đóng tới thời điểm dự báo.</p>
      <div className="stack" style={{ marginTop: 12 }}>
        {diagnostics.map((diag) => (
          <details key={diag.candidate_id} className="report-details">
            <summary>
              <span>
                {diag.pattern_id} <span className="hint">· quy tắc v{diag.rule_version}</span>
              </span>
              <Badge
                variant={
                  diag.overall_match_status === 'KHỚP_THEO_RULE_VERSION'
                    ? 'success'
                    : diag.overall_match_status === 'KHÔNG_KHỚP'
                      ? 'error'
                      : 'warning'
                }
              >
                {matchLabel(diag.overall_match_status)}
              </Badge>
            </summary>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Tiêu chí</th>
                    <th>Đo được</th>
                    <th>Điều kiện</th>
                    <th>Kết quả</th>
                  </tr>
                </thead>
                <tbody>
                  {diag.criteria.map((c) => (
                    <tr key={c.criterion_id}>
                      <td>
                        {c.description}
                        <div className="hint">{c.reason}</div>
                      </td>
                      <td>{c.measured_value}</td>
                      <td>{c.expected_relation}</td>
                      <td>
                        <Badge variant={c.status === 'PASS' ? 'success' : c.status === 'FAIL' ? 'error' : 'neutral'}>
                          {criterionLabel(c.status)}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {diag.conflicts.length > 0 && (
              <p className="hint">Mâu thuẫn: {diag.conflicts.join('; ')}</p>
            )}
            {diag.limitations.length > 0 && (
              <p className="hint">Giới hạn: {diag.limitations.join('; ')}</p>
            )}
          </details>
        ))}
      </div>
    </Card>
  );
}

function Sources({ sources, contradictions }: { sources: ResearchSourceItem[]; contradictions: string[] }) {
  return (
    <Card>
      <h2 className="card-title">Nguồn tài liệu</h2>
      <div className="stack" style={{ marginTop: 12 }}>
        {sources.map((s) => (
          <div key={s.source_id} className="card-flat">
            <div className="spread">
              <a href={s.url} target="_blank" rel="noopener noreferrer">
                {s.title}
              </a>
              <Badge variant={s.access_status === 'ACCESSIBLE' ? 'accent' : 'warning'}>
                {s.access_status === 'ACCESSIBLE' ? 'Đã đọc được' : 'Không truy cập được'}
              </Badge>
            </div>
            <div className="hint">
              {s.author_or_publisher}
              {s.section_locator ? ` · ${s.section_locator}` : ''}
            </div>
            {s.excerpt && <blockquote className="report-quote">{s.excerpt}</blockquote>}
          </div>
        ))}
        {contradictions.length > 0 && (
          <Notice variant="warning" title="Dữ kiện trái chiều:">
            <ul className="report-list">
              {contradictions.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          </Notice>
        )}
      </div>
    </Card>
  );
}

function SectionBody({ job, sectionKey, title, content }: { job: ExternalAnalysisJobDTO; sectionKey: string; title: string; content: string }) {
  const features = job.evidence_envelope?.feed?.features;
  const rows = sectionKey === 'cau_hoi_va_du_lieu' ? formatCanonicalFeatureTable(features) : [];

  return (
    <div className="report-prose">
      <ReactMarkdown>{cleanSectionContent(content, title)}</ReactMarkdown>
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Chỉ số</th>
                <th>Giá trị</th>
                <th>Ý nghĩa</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label}>
                  <td>{r.label}</td>
                  <td>
                    <strong>{r.valueStr}</strong>
                  </td>
                  <td className="muted">{r.unitMeaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function ReportView({ job, live = true, mock = false }: { job: ExternalAnalysisJobDTO; live?: boolean; mock?: boolean }) {
  const ai = job.ai_prediction;
  const inProgress = isInProgress(job.status);
  const failed = job.status === 'FAILED' || job.status === 'FAILED_INTERRUPTED';
  const envelope = job.evidence_envelope;
  const sections = envelope?.report_sections;
  const hasOutcome = job.outcome !== null && job.outcome !== 'PENDING';
  const sources = envelope?.research?.sources ?? [];
  const contradictions = envelope?.research?.contradictory_sources_or_facts ?? [];

  return (
    <div className="stack">
      {live && inProgress && <AutoRefresh />}

      {mock && (
        <Notice variant="warning" title="DỮ LIỆU GIẢ LẬP — chưa gọi Gemini.">
          Báo cáo này được tạo từ dữ liệu giả để chạy thử, không phải nhận định thật của Gemini. Đừng dùng để đánh giá chất lượng dự báo.
        </Notice>
      )}
      <Card>
        <div className="spread">
          <div>
            <h2 className="card-title">
              {job.symbol} · {job.timeframe} · dự báo {job.horizon_minutes} phút
            </h2>
            <p className="card-sub">Tạo lúc {formatIsoDateTime(job.created_at_iso)} (UTC+7)</p>
          </div>
          <Badge variant={statusVariant(job.status)}>{externalStatusLabel(job.status)}</Badge>
        </div>
        <div className="grid-4 report-meta">
          <Meta label="Thời điểm dự báo (t)" value={formatDateTimeTz(job.prediction_time_t_ms)} />
          <Meta label="Giá tại thời điểm" value={formatUsd(job.purchase_price_p)} />
          <Meta label="Dữ liệu đầu vào" value="6 giờ nến trước thời điểm dự báo" />
          <Meta label="Người xem" value={job.user_vote ? `Bạn chọn ${directionLabel(job.user_vote)}` : 'Chưa dự đoán'} />
        </div>
      </Card>

      {job.leakage_risk_banner && (
        <Notice variant="warning" title="Lưu ý:">
          Phân tích này viết sau thời điểm lịch sử nên mô hình có thể đã biết diễn biến thật. Đây là tham khảo, không phải dự
          báo đã kiểm chứng.
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
          Cần ít nhất 6 giờ nến liên tục trước thời điểm dự báo.
        </Notice>
      )}

      {ai && !failed && (
        <Card>
          <div className="spread">
            <h2 className="card-title">Nhận định hướng giá</h2>
            <DirectionPill direction={ai.direction} />
          </div>
          {ai.direction !== 'ABSTAIN' && (
            <p style={{ marginTop: 12 }}>
              Sau {job.horizon_minutes} phút, giá có thể <strong>{ai.direction === 'UP' ? 'cao hơn' : 'thấp hơn'}</strong> mức
              mua {formatUsd(job.purchase_price_p)}.
            </p>
          )}
          {ai.rationale && <p className="report-rationale">{ai.rationale}</p>}
          {ai.evidence_candle_times.length > 0 && (
            <div className="stack-sm" style={{ marginTop: 12 }}>
              <span className="label">Các nến được viện dẫn</span>
              <div className="row" style={{ gap: 6 }}>
                {ai.evidence_candle_times.map((t) => (
                  <span key={t} className="report-chip">
                    {formatDateTime(t)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {hasOutcome && (
        <Card>
          <h2 className="card-title">Kết quả thực tế</h2>
          <div className="grid-4 report-meta">
            <Meta label="Thị trường" value={outcomeLabel(job.outcome)} />
            <Meta label="Giá sau thời lượng dự báo" value={formatUsd(job.target_price)} />
            <div>
              <div className="stat-label">Phân tích</div>
              <div className="report-meta-value">
                {ai ? (
                  <Verdict correct={ai.direction === job.outcome} abstained={ai.direction === 'ABSTAIN'} />
                ) : (
                  'Chưa có dữ liệu'
                )}
              </div>
            </div>
            <div>
              <div className="stat-label">Bạn</div>
              <div className="report-meta-value">
                {job.user_vote ? <Verdict correct={job.user_vote === job.outcome} /> : 'Chưa dự đoán'}
              </div>
            </div>
          </div>
        </Card>
      )}

      {sections &&
        SECTION_DEFS.map((def, i) => {
          const content = sections[def.key];
          if (!content) return null;
          return (
            <Card key={def.key}>
              <h2 className="card-title">
                {i + 1}. {def.title}
              </h2>
              <SectionBody job={job} sectionKey={def.key} title={def.title} content={content} />
            </Card>
          );
        })}

      {envelope?.diagnostics && envelope.diagnostics.length > 0 && <PatternChecks diagnostics={envelope.diagnostics} />}
      {(sources.length > 0 || contradictions.length > 0) && <Sources sources={sources} contradictions={contradictions} />}

      {ai && (
        <details className="report-details report-tech">
          <summary>Chi tiết kỹ thuật</summary>
          <p className="hint">
            Mô hình: {ai.model_id} · Phiên bản lời nhắc: {ai.prompt_version} · Mã tác vụ: {job.id}
          </p>
        </details>
      )}
    </div>
  );
}
