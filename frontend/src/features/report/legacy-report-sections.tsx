import ReactMarkdown from 'react-markdown';
import { Badge, Card, Notice } from '@/shared/ui/primitives';
import { directionArrow, directionLabel, formatDateTime, formatUsd } from '@/shared/format';
import type {
  ExternalAnalysisJobDTO,
  PatternDiagnostic,
  ReportSections,
  ResearchSourceItem,
} from '../replay/external-types';
import { cleanSectionContent, formatCanonicalFeatureTable } from './report-format';
import { criterionLabel, matchLabel } from './labels';

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
                  {diag.criteria.map((criterion) => (
                    <tr key={criterion.criterion_id}>
                      <td>
                        {criterion.description}
                        <div className="hint">{criterion.reason}</div>
                      </td>
                      <td>{criterion.measured_value}</td>
                      <td>{criterion.expected_relation}</td>
                      <td>
                        <Badge
                          variant={
                            criterion.status === 'PASS'
                              ? 'success'
                              : criterion.status === 'FAIL'
                                ? 'error'
                                : 'neutral'
                          }
                        >
                          {criterionLabel(criterion.status)}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
        {sources.map((source) => (
          <div key={source.source_id} className="card-flat">
            <div className="spread">
              <a href={source.url} target="_blank" rel="noopener noreferrer">
                {source.title}
              </a>
              <Badge variant={source.access_status === 'ACCESSIBLE' ? 'accent' : 'warning'}>
                {source.access_status === 'ACCESSIBLE' ? 'Đã đọc được' : 'Không truy cập được'}
              </Badge>
            </div>
            <div className="hint">
              {source.author_or_publisher}
              {source.section_locator ? ` · ${source.section_locator}` : ''}
            </div>
            {source.excerpt && <blockquote className="report-quote">{source.excerpt}</blockquote>}
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
              {rows.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>
                    <strong>{row.valueStr}</strong>
                  </td>
                  <td className="muted">{row.unitMeaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function LegacyDirectionCard({ job }: { job: ExternalAnalysisJobDTO }) {
  const ai = job.ai_prediction;
  if (!ai) return null;
  return (
    <Card>
      <div className="spread">
        <h2 className="card-title">Nhận định hướng giá</h2>
        <DirectionPill direction={ai.direction} />
      </div>
      {ai.direction !== 'ABSTAIN' && (
        <p style={{ marginTop: 12 }}>
          Sau {job.horizon_minutes} phút, giá có thể{' '}
          <strong>{ai.direction === 'UP' ? 'cao hơn' : 'thấp hơn'}</strong> mức mua{' '}
          {formatUsd(job.purchase_price_p)}.
        </p>
      )}
      {ai.rationale && <p className="report-rationale">{ai.rationale}</p>}
      {ai.evidence_candle_times.length > 0 && (
        <div className="stack-sm" style={{ marginTop: 12 }}>
          <span className="label">Các nến được viện dẫn</span>
          <div className="row" style={{ gap: 6 }}>
            {ai.evidence_candle_times.map((time) => (
              <span key={time} className="report-chip">
                {formatDateTime(time)}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

export function LegacyReportSections({ job }: { job: ExternalAnalysisJobDTO }) {
  const envelope = job.evidence_envelope;
  const sections = envelope?.report_sections;
  const sources = envelope?.research?.sources ?? [];
  const contradictions = envelope?.research?.contradictory_sources_or_facts ?? [];
  const diagnostics = envelope?.diagnostics ?? [];

  return (
    <>
      {sections &&
        SECTION_DEFS.map((def, index) => {
          const content = sections[def.key];
          if (!content) return null;
          return (
            <Card key={def.key}>
              <h2 className="card-title">
                {index + 1}. {def.title}
              </h2>
              <SectionBody job={job} sectionKey={def.key} title={def.title} content={content} />
            </Card>
          );
        })}
      {diagnostics.length > 0 && <PatternChecks diagnostics={diagnostics} />}
      {(sources.length > 0 || contradictions.length > 0) && (
        <Sources sources={sources} contradictions={contradictions} />
      )}
    </>
  );
}
