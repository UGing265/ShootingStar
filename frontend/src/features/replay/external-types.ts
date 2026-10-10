export type ExternalAnalysisStatus =
  | 'PREPARING'
  | 'CALLING'
  | 'READY'
  | 'ABSTAIN'
  | 'FAILED'
  | 'INSUFFICIENT_HISTORY'
  | 'UNSCORABLE';

export type ExternalContextVariant = 'A' | 'B';
export type ExternalAnalysisMode = 'RETROSPECTIVE' | 'PROSPECTIVE';

export interface ExternalModelPredictionOutput {
  direction: 'UP' | 'DOWN' | 'ABSTAIN';
  rationale: string;
  evidence_candle_times: number[];
  lesson_ids: string[];
  probability_up: number | null;
  probability_down: number | null;
  model_id: string;
  prompt_version: string;
  key_index?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  estimated_cost_usd?: number | null;
}

export interface ExternalAnalysisJobDTO {
  id: string;
  snapshot_id: string;
  snapshot_hash: string;
  symbol: string;
  timeframe: string;
  prediction_time_t_ms: number;
  purchase_price_p: number;
  horizon_minutes: number;
  context_variant: ExternalContextVariant;
  mode: ExternalAnalysisMode;
  status: ExternalAnalysisStatus;
  created_at_ms: number;
  ai_prediction: ExternalModelPredictionOutput | null;
  user_vote: 'UP' | 'DOWN' | null;
  outcome: 'UP' | 'DOWN' | 'FLAT' | 'PENDING' | 'UNSCORABLE' | null;
  target_price: number | null;
  outcome_evaluated_at_ms: number | null;
  error_message: string | null;
  leakage_risk_banner: boolean;
}
