export interface SignalSummary {
  id: string;
  prediction_time_ms: number;
  symbol: string;
  timeframe: string;
  horizon_minutes: number;
  predicted_class: string;
  decision: string;
  decision_reason: string;
  probability_up: number;
  probability_down: number;
  probability_no_trade: number;
  status: string; // PENDING, EVALUATED, UNSCORABLE
  realized_label: string | null;
  realized_return: number | null;
  is_match: boolean | null;
  unscorable_reason: string | null;
  created_at: string;
}

export interface SignalPredictionDTO {
  id: string;
  prediction_time_ms: number;
  experiment_id: string;
  symbol: string;
  timeframe: string;
  horizon_minutes: number;
  probability_up: number;
  probability_down: number;
  probability_no_trade: number;
  predicted_class: string;
  decision: string;
  decision_reason: string;
  created_at: string;
}

export interface SignalOutcomeDTO {
  id: string;
  status: string;
  evaluated_at_ms: number;
  realized_return: number | null;
  realized_label: string | null;
  is_match: boolean | null;
  unscorable_reason: string | null;
  created_at: string;
}

export interface ReviewOverrideDTO {
  id: string;
  reviewer_id: string;
  override_decision: string;
  notes: string;
  created_at: string;
}

export interface AuditLogDTO {
  id: number;
  action: string;
  details: Record<string, any>;
  created_at: string;
}

export interface SignalDetailResponse {
  prediction: SignalPredictionDTO;
  outcome: SignalOutcomeDTO | null;
  reviews: ReviewOverrideDTO[];
  audit_logs: AuditLogDTO[];
}
