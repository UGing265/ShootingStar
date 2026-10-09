export interface PatternRuleDTO {
  id: string;
  name: string;
  version: number;
  description: string;
  definition: Record<string, any>;
  created_at: string;
}

export interface PatternHitDTO {
  id: string;
  rule_id: string;
  detected_time_ms: number;
  symbol: string;
  timeframe: string;
  outcome_return_30m: number | null;
  outcome_label: string | null;
  created_at: string;
}

export interface PatternDetailResponse {
  rule: PatternRuleDTO;
  hits: PatternHitDTO[];
}
