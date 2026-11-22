export type ExternalAnalysisStatus =
  | 'PREPARING'
  | 'PREPARING_FEED'
  | 'ANALYZING'
  | 'RESEARCHING'
  | 'MATCHING'
  | 'SYNTHESIZING'
  | 'CALLING'
  | 'READY'
  | 'ABSTAIN'
  | 'RESEARCH_INCOMPLETE'
  | 'FAILED'
  | 'FAILED_INTERRUPTED'
  | 'INSUFFICIENT_HISTORY'
  | 'UNSCORABLE';

export type ExternalContextVariant = 'A' | 'B';
export type ExternalAnalysisMode = 'RETROSPECTIVE' | 'PROSPECTIVE';

export interface ExternalModelPredictionOutput {
  direction: 'UP' | 'DOWN' | 'ABSTAIN';
  rationale: string;
  evidence_candle_times: number[];
  model_id: string;
  prompt_version: string;
}

export interface PatternCriterion {
  criterion_id: string;
  description: string;
  measured_value: number;
  expected_relation: string;
  status: 'PASS' | 'FAIL' | 'UNKNOWN';
  reason: string;
}

export interface PatternDiagnostic {
  pattern_id: string;
  candidate_id: string;
  rule_version: string;
  shape_status: 'PASS' | 'FAIL' | 'UNKNOWN';
  context_status: 'PASS' | 'FAIL' | 'UNKNOWN';
  confirmation_status: string;
  overall_match_status: 'KHỚP_THEO_RULE_VERSION' | 'KHÔNG_KHỚP' | 'CHƯA_ĐỦ_TIÊU_CHÍ';
  conflicts: string[];
  limitations: string[];
  criteria: PatternCriterion[];
}

export interface ResearchSourceItem {
  source_id: string;
  url: string;
  title: string;
  author_or_publisher: string;
  source_type: string;
  access_status: string;
  section_locator: string;
  excerpt: string;
}

export interface ReportSections {
  cau_hoi_va_du_lieu?: string;
  dien_bien_quan_sat?: string;
  gia_thuyet_va_mau_duoc_kiem?: string;
  tai_lieu_da_tra?: string;
  lap_luan_va_phan_bien?: string;
  ket_luan_co_dieu_kien?: string;
  gioi_han_va_kha_nang_ap_dung?: string;
}

export interface EvidenceEnvelopeDTO {
  protocol_version: string;
  feed?: { features?: Array<{ feature_id: string; value: number }> } & Record<string, unknown>;
  research?: {
    search_provider?: string;
    queries_executed?: string[];
    sources?: ResearchSourceItem[];
    contradictory_sources_or_facts?: string[];
    unresolved_questions?: string[];
  };
  diagnostics?: PatternDiagnostic[];
  report_sections?: ReportSections;
  final_direction?: 'UP' | 'DOWN' | 'ABSTAIN';
}

export interface ExternalAnalysisJobDTO {
  id: string;
  snapshot_id: string;
  symbol: string;
  timeframe: string;
  prediction_time_t_ms: number;
  purchase_price_p: number;
  horizon_minutes: number;
  context_variant: ExternalContextVariant;
  mode: ExternalAnalysisMode;
  status: ExternalAnalysisStatus;
  created_at_iso: string;
  ai_prediction: ExternalModelPredictionOutput | null;
  user_vote: 'UP' | 'DOWN' | null;
  outcome: 'UP' | 'DOWN' | 'FLAT' | 'PENDING' | 'UNSCORABLE' | null;
  target_price: number | null;
  outcome_evaluated_at_ms: number | null;
  error_message: string | null;
  leakage_risk_banner: boolean;
  evidence_envelope?: EvidenceEnvelopeDTO | null;
}
