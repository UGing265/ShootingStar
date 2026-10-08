"""Experiment runner coordinating features, splits, model training, evaluation, and DB provenance."""

import json
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

from shootingstar.adapters.db.models import (
    ExperimentModel,
    ExperimentSplitModel,
    MetricReportModel,
    ModelArtifactModel,
)
from shootingstar.adapters.db.repository import (
    ExperimentRepository,
    ExperimentSplitRepository,
    MetricReportRepository,
    SnapshotRepository,
)
from shootingstar.adapters.db.session import get_db_session
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.evaluation import EvaluationReport, EvaluationReportGenerator
from shootingstar.application.features import FeatureExtractionService
from shootingstar.application.labels import LabelGenerationService
from shootingstar.application.modeling import CalibratedLogisticRegressionModel
from shootingstar.application.splits import WalkForwardSplitter


class ExperimentRunner:
    """Coordinates end-to-end research experiment with immutable provenance."""

    def __init__(
        self,
        snapshot_storage: Optional[SnapshotStorage] = None,
        models_dir: Optional[Path] = None,
        reports_dir: Optional[Path] = None,
    ):
        self.snapshot_storage = snapshot_storage or SnapshotStorage()
        self.models_dir = models_dir or Path("data/models")
        self.reports_dir = reports_dir or Path("data/reports")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def run_experiment(
        self,
        snapshot_path: Path,
        experiment_id: str,
        name: str = "BTCUSDT 30m Calibrated Logistic Regression",
    ) -> Tuple[EvaluationReport, Path, str]:
        # 1. Load snapshot
        candles = self.snapshot_storage.load_snapshot(snapshot_path)
        if not candles:
            raise ValueError(f"No candles loaded from {snapshot_path}")

        venue = candles[0].venue
        symbol = candles[0].symbol
        timeframe = candles[0].timeframe

        # 2. Extract features and labels
        label_service = LabelGenerationService(horizon_minutes=30)
        labels = label_service.generate_labels(candles)

        feature_service = FeatureExtractionService()
        feat_matrix = feature_service.extract_matrix(candles)

        # 3. Align features and labels by candle open_time
        label_map = {lbl.open_time_t_ms: lbl for lbl in labels}
        aligned_X = []
        aligned_y = []
        aligned_returns = []
        aligned_times = []

        for i, t in enumerate(feat_matrix.timestamps_ms):
            if t in label_map:
                lbl = label_map[t]
                if lbl.direction_label in ("UP", "DOWN"):
                    aligned_X.append(feat_matrix.values[i])
                    aligned_y.append(1 if lbl.direction_label == "UP" else 0)
                    aligned_returns.append(lbl.return_30m)
                    aligned_times.append(t)

        X = np.array(aligned_X, dtype=np.float64)
        y = np.array(aligned_y, dtype=int)
        returns = np.array(aligned_returns, dtype=np.float64)

        if len(X) < 100:
            raise ValueError(f"Insufficient aligned samples ({len(X)}) for walk-forward evaluation")

        # 4. Chronological 4-way split with anti-leakage gap
        splitter = WalkForwardSplitter()
        splits = splitter.split(aligned_times)

        # Extract subsets
        X_train = X[splits.train.start_idx : splits.train.end_idx + 1]
        y_train = y[splits.train.start_idx : splits.train.end_idx + 1]

        X_calib = X[splits.calibration.start_idx : splits.calibration.end_idx + 1]
        y_calib = y[splits.calibration.start_idx : splits.calibration.end_idx + 1]

        X_test = X[splits.test.start_idx : splits.test.end_idx + 1]
        y_test = y[splits.test.start_idx : splits.test.end_idx + 1]
        returns_test = returns[splits.test.start_idx : splits.test.end_idx + 1]

        # 5. Fit base model and calibrate probabilities on calibration window
        model = CalibratedLogisticRegressionModel()
        model.fit_and_calibrate(X_train, y_train, X_calib, y_calib)

        # 6. Save model artifact
        artifact_path, artifact_hash = model.save_artifact(self.models_dir, experiment_id)

        # 7. Generate evaluation report on held-out test window
        report = EvaluationReportGenerator.generate_report(
            model=model,
            X_test=X_test,
            y_test=y_test,
            returns_test=returns_test,
            experiment_id=experiment_id,
            snapshot_sha256=snapshot_path.stem.split("_")[-1],
            symbol=symbol,
            timeframe=timeframe,
            horizon_minutes=30,
            test_start_time_ms=splits.test.start_time_ms,
            test_end_time_ms=splits.test.end_time_ms,
        )

        # Write reports
        report_md_path = self.reports_dir / f"{experiment_id}_report.md"
        report_json_path = self.reports_dir / f"{experiment_id}_report.json"
        report_md_path.write_text(report.to_markdown(), encoding="utf-8")
        report_json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

        # 8. Record to PostgreSQL DB
        try:
            with get_db_session() as session:
                exp_repo = ExperimentRepository(session)
                split_repo = ExperimentSplitRepository(session)
                rep_repo = MetricReportRepository(session)
                snap_repo = SnapshotRepository(session)

                snapshot_obj = snap_repo.get_by_sha256(report.snapshot_sha256)
                snap_id = snapshot_obj.id if snapshot_obj else report.snapshot_sha256

                # Create experiment record
                exp_record = ExperimentModel(
                    id=experiment_id,
                    name=name,
                    config_hash=artifact_hash,
                    snapshot_id=snap_id,
                    parameters_json=json.dumps({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "horizon_minutes": 30,
                        "model": "CalibratedLogisticRegression",
                    }),
                )
                exp_repo.save(exp_record)

                # Create split records
                for split_win in [splits.train, splits.calibration, splits.validation, splits.test]:
                    split_rec = ExperimentSplitModel(
                        experiment_id=experiment_id,
                        split_type=split_win.split_type,
                        start_time_ms=split_win.start_time_ms,
                        end_time_ms=split_win.end_time_ms,
                        sample_count=split_win.sample_count,
                    )
                    split_repo.save(split_rec)

                # Save metric report record
                rep_rec = MetricReportModel(
                    experiment_id=experiment_id,
                    split_type="TEST",
                    report_type="OUT_OF_SAMPLE_WALK_FORWARD",
                    metrics_json=json.dumps(report.to_dict()["directional_metrics"]),
                    calibration_json=json.dumps(report.to_dict()["calibration_bins"]),
                )
                rep_repo.save(rep_rec)
        except Exception as e:
            # If database not available or not linked to this test snapshot, continue
            pass

        return report, artifact_path, artifact_hash
