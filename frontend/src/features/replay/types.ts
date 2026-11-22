/** Entry-strategy replay job (POST /replay/jobs). */

export interface SimulationAIPredictionDTO {
  predicted_direction: string;
  evidence_summary: string | null;
}

export interface SimulationUserVoteDTO {
  user_direction: 'UP' | 'DOWN';
  voted_at_utc: string;
  is_locked: boolean;
}

export interface SimulationOutcomeDTO {
  status: 'EVALUATED' | 'PENDING' | 'UNSCORABLE';
  horizon_time_ms: number;
  future_price: number | null;
  price_change_pct: number | null;
  market_direction: 'UP' | 'DOWN' | 'FLAT' | null;
  user_is_correct: boolean | null;
  unscorable_reason: string | null;
  revealed_at_utc: string | null;
}

export interface StrategyEvaluationDTO {
  strategy_version: string;
  candidate_state: string;
  decision: string;
  reasons: string[];
  proposed_entry: number | null;
  zone_low?: number | null;
  zone_high?: number | null;
  target_price: number | null;
  stop_price: number | null;
  reward_risk_ratio: number | null;
  support_level: number | null;
  reclaim_level: number | null;
  is_trade_eligible: boolean;
}

export interface StrategyOutcomeDTO {
  trade_executed: boolean;
  outcome?: 'TP_FIRST' | 'SL_FIRST' | 'TIMEOUT' | 'AMBIGUOUS' | 'CENSORED' | 'UNSCORABLE' | 'NO_TRADE' | 'UNFILLED';
  entry_price?: number | null;
  exit_price?: number | null;
  entry_time_ms?: number | null;
  exit_time_ms?: number | null;
  gross_return_pct?: number | null;
  net_return_pct?: number | null;
  fee_rate_bps?: number | null;
  slippage_bps?: number | null;
  is_cost_gated?: boolean;
  note?: string;
  reason?: string;
}

export interface SimulationJobResponse {
  job_id: string;
  snapshot_id: string;
  symbol: string;
  timeframe: string;
  buy_time_ms: number;
  buy_price: number;
  candle_close_at_buy: number;
  price_offset_pct: number;
  horizon_minutes: number;
  status: 'AI_PREDICTED' | 'VOTED' | 'REVEALED' | 'FAILED';
  created_at_utc: string;
  ai_prediction: SimulationAIPredictionDTO | null;
  user_vote: SimulationUserVoteDTO | null;
  outcome: SimulationOutcomeDTO | null;
  strategy_evaluation?: StrategyEvaluationDTO | null;
  strategy_outcome?: StrategyOutcomeDTO | null;
}
