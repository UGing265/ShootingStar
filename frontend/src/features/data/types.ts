export interface IngestionRunSummary {
  id: string;
  venue: string;
  symbol: string;
  timeframe: string;
  start_time_ms: number;
  end_time_ms: number;
  valid_candles_count: number;
  missing_intervals_count: number;
  duplicate_candles_count: number;
  coverage_ratio: number;
  is_pristine: boolean;
  raw_files_count: number;
  created_at: string;
}

export interface SnapshotSummary {
  id: string;
  ingestion_run_id: string | null;
  venue: string;
  symbol: string;
  timeframe: string;
  candle_count: number;
  start_time_ms: number;
  end_time_ms: number;
  sha256: string;
  created_at: string;
}

export interface SnapshotQualityResponse {
  snapshot_id: string;
  sha256: string;
  venue: string;
  symbol: string;
  timeframe: string;
  candle_count: number;
  start_time_ms: number;
  end_time_ms: number;
  ingestion_run_id: string | null;
  coverage_ratio: number | null;
  missing_intervals_count: number | null;
  duplicate_candles_count: number | null;
  is_pristine: boolean | null;
  quality_status: string;
  gap_list_status: string;
  missing_timestamps: number[];
  created_at: string;
}

export interface CandleDTO {
  open_time_ms: number;
  close_time_ms: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  quote_volume: number;
  trades_count: number;
}
