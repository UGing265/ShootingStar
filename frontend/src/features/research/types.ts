export interface ExperimentSummary {
  id: string;
  name: string;
  config_hash: string;
  snapshot_id: string;
  parameters: Record<string, unknown>;
  created_at: string;
}

export interface ExperimentSplitDTO {
  id: string;
  split_type: string;
  start_time_ms: number;
  end_time_ms: number;
  sample_count: number;
}

export interface CalibrationBinDTO {
  bin_index: number;
  bin_range: string;
  sample_count: number;
  mean_predicted_prob: number;
  empirical_frequency: number;
}

export interface CalibrationReportDTO {
  bins: CalibrationBinDTO[];
}

export interface MetricReportDTO {
  id: string;
  split_type: string;
  report_type: string;
  metrics: Record<string, unknown>;
  calibration?: CalibrationReportDTO | null;
  created_at: string;
}

export interface ModelArtifactDTO {
  id: string;
  model_type: string;
  artifact_hash: string;
  created_at: string;
}

export interface ExperimentDetailResponse {
  id: string;
  name: string;
  config_hash: string;
  snapshot_id: string;
  snapshot_sha256?: string | null;
  parameters: Record<string, unknown>;
  created_at: string;
  splits: ExperimentSplitDTO[];
  artifacts: ModelArtifactDTO[];
  reports: MetricReportDTO[];
}
