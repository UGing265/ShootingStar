"""Experiment runner coordinating features, splits, model training, evaluation, and DB provenance."""

import hashlib
import json
import logging
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

from shootingstar.adapters.db.models import (
    ExperimentModel,
    ExperimentSplitModel,
    MetricReportModel,
    ModelArtifactModel,
    SnapshotModel,
)
from shootingstar.adapters.db.repository import (
    ExperimentRepository,
    ExperimentSplitRepository,
    MetricReportRepository,
    ModelArtifactRepository,
    SnapshotRepository,
)
from shootingstar.adapters.db.session import get_db_session
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.evaluation import EvaluationReport, EvaluationReportGenerator
from shootingstar.application.features import FeatureExtractionService
from shootingstar.application.labels import LabelGenerationService
from shootingstar.application.modeling import CalibratedLogisticRegressionModel
from shootingstar.application.splits import RollingWindowSplitter, WalkForwardSplitter

class ExperimentRunner:
    """Coordinates end-to-end research experiment with immutable provenance."""

    def __init__(
        self,
        snapshot_storage: Optional[SnapshotStorage] = None,
        models_dir: Optional[Path] = None,
        reports_dir: Optional[Path] = None,
        assumed_latency_ms: int = 1,
    ):
        self.snapshot_storage = snapshot_storage or SnapshotStorage()
        self.models_dir = models_dir or Path("data/models")
        self.reports_dir = reports_dir or Path("data/reports")
        self.assumed_latency_ms = assumed_latency_ms
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
        label_service = LabelGenerationService(
            horizon_minutes=30,
            assumed_latency_ms=self.assumed_latency_ms,
        )
        labels = label_service.generate_labels(candles)

        feature_service = FeatureExtractionService(assumed_latency_ms=self.assumed_latency_ms)
        feat_matrix = feature_service.extract_matrix(candles)

        # 3. Align features and labels by candle open_time
        label_map = {lbl.open_time_t_ms: lbl for lbl in labels}
        aligned_X = []
        aligned_y = []
        aligned_returns = []
        aligned_times = []

        for i, open_t in enumerate(feat_matrix.candle_open_times_ms):
            if open_t in label_map:
                lbl = label_map[open_t]
                avail_t = feat_matrix.timestamps_ms[i]
                # Strict causal contract: feature must be available at or before trade entry time
                if lbl.entry_time_ms < avail_t:
                    continue
                if lbl.direction_label in ("UP", "DOWN"):
                    aligned_X.append(feat_matrix.values[i])
                    aligned_y.append(1 if lbl.direction_label == "UP" else 0)
                    aligned_returns.append(lbl.return_30m)
                    aligned_times.append(avail_t)
        X = np.array(aligned_X, dtype=np.float64)
        y = np.array(aligned_y, dtype=int)
        returns = np.array(aligned_returns, dtype=np.float64)

        if len(X) < 100:
            raise ValueError(f"Insufficient aligned samples ({len(X)}) for walk-forward evaluation")

        # 4. Chronological 4-way split with anti-leakage gap derived from timeframe and horizon
        splitter = WalkForwardSplitter.for_timeframe(timeframe=timeframe, horizon_minutes=30)
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
        full_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
        report = EvaluationReportGenerator.generate_report(
            model=model,
            X_test=X_test,
            y_test=y_test,
            returns_test=returns_test,
            experiment_id=experiment_id,
            snapshot_sha256=full_sha256,
            symbol=symbol,
            timeframe=timeframe,
            horizon_minutes=30,
            test_start_time_ms=splits.test.start_time_ms,
            test_end_time_ms=splits.test.end_time_ms,
            y_train=y_train,
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
                if not snapshot_obj:
                    snapshot_obj = SnapshotModel(
                        id=report.snapshot_sha256,
                        venue="BINANCE",
                        symbol=symbol,
                        timeframe=timeframe,
                        start_time_ms=candles[0].open_time_ms,
                        end_time_ms=candles[-1].close_time_ms,
                        candle_count=len(candles),
                        file_path=str(snapshot_path),
                        sha256=report.snapshot_sha256,
                    )
                    snap_repo.save(snapshot_obj)
                snap_id = snapshot_obj.id

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
                        "assumed_latency_ms": self.assumed_latency_ms,
                        "availability_contract": "PROVENANCED_LATENCY_GATED",
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
                metrics_dict = dict(report.to_dict()["directional_metrics"])
                metrics_dict["assumed_latency_ms"] = self.assumed_latency_ms
                rep_rec = MetricReportModel(
                    experiment_id=experiment_id,
                    split_type="TEST",
                    report_type="OUT_OF_SAMPLE_WALK_FORWARD",
                    metrics_json=json.dumps(metrics_dict),
                    calibration_json=json.dumps(report.to_dict()["calibration_bins"]),
                )
                rep_repo.save(rep_rec)

                # Save model artifact record
                art_repo = ModelArtifactRepository(session)
                existing_art = art_repo.get_by_id(artifact_hash)
                if not existing_art:
                    art_rec = ModelArtifactModel(
                        id=artifact_hash,
                        experiment_id=experiment_id,
                        model_type="CalibratedLogisticRegression",
                        artifact_path=str(artifact_path),
                        artifact_hash=artifact_hash,
                        metrics_json=json.dumps(metrics_dict),
                    )
                    art_repo.save(art_rec)
        except Exception as e:
            logger.warning("DB persistence failed for experiment %s: %s", experiment_id, e)
            if os.environ.get("SHOOTINGSTAR_DATABASE_URL"):
                raise

        return report, artifact_path, artifact_hash


@dataclass(frozen=True)
class WindowEvaluationResult:
    window_name: str
    is_eligible: bool
    train_start_ms: Optional[int]
    train_end_ms: Optional[int]  # Training Cutoff t_train
    sample_count: int
    validation_accuracy: Optional[float]
    directional_accuracy: Optional[float]
    brier_score: Optional[float]
    log_loss: Optional[float]
    baseline_always_up_accuracy: Optional[float]
    baseline_majority_accuracy: Optional[float]
    baseline_momentum_accuracy: Optional[float]
    artifact_path: Optional[str]
    artifact_hash: Optional[str]
    is_selected_winner: bool = False
    ineligibility_reason: Optional[str] = None


@dataclass(frozen=True)
class MultiWindowStudyReport:
    study_id: str
    snapshot_path: str
    timeframe: str
    test_start_ms: int
    test_end_ms: int
    test_samples_count: int
    results: List[WindowEvaluationResult]

    def to_dict(self) -> dict:
        return {
            "study_id": self.study_id,
            "snapshot_path": self.snapshot_path,
            "timeframe": self.timeframe,
            "test_start_ms": self.test_start_ms,
            "test_end_ms": self.test_end_ms,
            "test_samples_count": self.test_samples_count,
            "results": [
                {
                    "window_name": r.window_name,
                    "is_eligible": r.is_eligible,
                    "train_start_ms": r.train_start_ms,
                    "train_end_ms": r.train_end_ms,
                    "sample_count": r.sample_count,
                    "validation_accuracy": r.validation_accuracy,
                    "directional_accuracy": r.directional_accuracy,
                    "brier_score": r.brier_score,
                    "log_loss": r.log_loss,
                    "baseline_always_up_accuracy": r.baseline_always_up_accuracy,
                    "baseline_majority_accuracy": r.baseline_majority_accuracy,
                    "baseline_momentum_accuracy": r.baseline_momentum_accuracy,
                    "artifact_hash": r.artifact_hash,
                    "is_selected_winner": r.is_selected_winner,
                    "ineligibility_reason": r.ineligibility_reason,
                }
                for r in self.results
            ],
        }


class MultiWindowStudyRunner:
    """Runs comparative research across candidate training history lengths on identical test data."""

    def __init__(
        self,
        snapshot_storage: Optional[SnapshotStorage] = None,
        models_dir: Optional[Path] = None,
        reports_dir: Optional[Path] = None,
        assumed_latency_ms: int = 1,
    ):
        self.snapshot_storage = snapshot_storage or SnapshotStorage()
        self.models_dir = models_dir or Path("data/models")
        self.reports_dir = reports_dir or Path("data/reports")
        self.assumed_latency_ms = assumed_latency_ms
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def run_study(
        self,
        snapshot_path: Path,
        study_id: str,
        candidate_window_days: Optional[List[int]] = None,
        test_period_days: int = 7,
    ) -> MultiWindowStudyReport:
        candidate_days = candidate_window_days or [30, 90, 180]
        candles = self.snapshot_storage.load_snapshot(snapshot_path)
        if not candles:
            raise ValueError(f"No candles loaded from {snapshot_path}")

        timeframe = candles[0].timeframe

        # Generate labels and features
        label_service = LabelGenerationService(
            horizon_minutes=30,
            assumed_latency_ms=self.assumed_latency_ms,
        )
        labels = label_service.generate_labels(candles)

        feature_service = FeatureExtractionService(assumed_latency_ms=self.assumed_latency_ms)
        feat_matrix = feature_service.extract_matrix(candles)

        # Align features and labels by candle open_time
        label_map = {lbl.open_time_t_ms: lbl for lbl in labels}
        aligned_X = []
        aligned_y = []
        aligned_times = []

        for i, open_t in enumerate(feat_matrix.candle_open_times_ms):
            if open_t in label_map:
                lbl = label_map[open_t]
                avail_t = feat_matrix.timestamps_ms[i]
                if lbl.entry_time_ms < avail_t:
                    continue
                if lbl.direction_label in ("UP", "DOWN"):
                    aligned_X.append(feat_matrix.values[i])
                    aligned_y.append(1 if lbl.direction_label == "UP" else 0)
                    aligned_times.append(avail_t)

        X = np.array(aligned_X, dtype=np.float64)
        y = np.array(aligned_y, dtype=int)

        if len(X) < 100:
            raise ValueError(f"Insufficient aligned samples ({len(X)}) for multi-window evaluation")

        # Build rolling windows
        splitter = RollingWindowSplitter(
            candidate_window_days=candidate_days,
            test_period_days=test_period_days,
            timeframe=timeframe,
            horizon_minutes=30,
        )

        periods = splitter.generate_periods(aligned_times, num_periods=1)
        if not periods:
            raise ValueError(f"Snapshot history span is insufficient for study with candidate windows {candidate_days}")

        period = periods[0]
        test_win = period.candidate_splits[0].test
        X_test = X[test_win.start_idx : test_win.end_idx + 1]
        y_test = y[test_win.start_idx : test_win.end_idx + 1]

        # Evaluate test-level baselines (Always-UP and Momentum)
        always_up_acc = float(np.mean(y_test == 1))
        momentum_preds = (X_test[:, 1] > 0).astype(int)
        momentum_acc = float(np.mean(y_test == momentum_preds))

        # Step 1: Fit and evaluate all candidate windows strictly on VALIDATION window
        candidates_state = []
        for cand in period.candidate_splits:
            if not cand.is_eligible or cand.train is None or cand.calibration is None or cand.validation is None:
                candidates_state.append({
                    "cand": cand,
                    "is_eligible": False,
                    "val_acc": -1.0,
                    "model": None,
                    "y_train": None,
                })
                continue

            X_train = X[cand.train.start_idx : cand.train.end_idx + 1]
            y_train = y[cand.train.start_idx : cand.train.end_idx + 1]
            X_calib = X[cand.calibration.start_idx : cand.calibration.end_idx + 1]
            y_calib = y[cand.calibration.start_idx : cand.calibration.end_idx + 1]

            model = CalibratedLogisticRegressionModel()
            model.fit_and_calibrate(X_train, y_train, X_calib, y_calib)

            # Evaluate strictly on VALIDATION set for model selection
            X_val = X[cand.validation.start_idx : cand.validation.end_idx + 1]
            y_val = y[cand.validation.start_idx : cand.validation.end_idx + 1]
            val_preds = model.predict(X_val)
            val_acc = float(np.mean(val_preds == y_val))

            candidates_state.append({
                "cand": cand,
                "is_eligible": True,
                "val_acc": val_acc,
                "model": model,
                "y_train": y_train,
            })

        # Step 2: Select frozen winning candidate window on validation performance
        eligible_states = [s for s in candidates_state if s["is_eligible"]]
        winner_window_name = None
        if eligible_states:
            winner_state = max(eligible_states, key=lambda s: s["val_acc"])
            winner_window_name = winner_state["cand"].window_name

        # Step 3: Evaluate ONLY the selected winner on the untouched test set
        results: List[WindowEvaluationResult] = []
        for s in candidates_state:
            cand = s["cand"]
            if not s["is_eligible"]:
                results.append(
                    WindowEvaluationResult(
                        window_name=cand.window_name,
                        is_eligible=False,
                        train_start_ms=None,
                        train_end_ms=None,
                        sample_count=0,
                        validation_accuracy=None,
                        directional_accuracy=None,
                        brier_score=None,
                        log_loss=None,
                        baseline_always_up_accuracy=always_up_acc,
                        baseline_majority_accuracy=None,
                        baseline_momentum_accuracy=momentum_acc,
                        artifact_path=None,
                        artifact_hash=None,
                        is_selected_winner=False,
                        ineligibility_reason=cand.ineligibility_reason,
                    )
                )
                continue

            model = s["model"]
            y_train = s["y_train"]
            val_acc = s["val_acc"]
            is_winner = (cand.window_name == winner_window_name)

            # Derive majority class strictly from training data
            majority_class = 1 if np.mean(y_train) >= 0.5 else 0
            majority_acc = float(np.mean(y_test == majority_class))

            # Save versioned candidate artifact with immutable manifest
            art_path, art_hash = model.save_artifact(self.models_dir, f"{study_id}_{cand.window_name}")

            # Only score on held-out test if candidate is the selected winner!
            if is_winner:
                preds = model.predict(X_test)
                probs_up = model.predict_proba(X_test)[:, 1]
                test_acc = float(np.mean(preds == y_test))
                test_brier = float(np.mean((probs_up - y_test) ** 2))
                eps = 1e-15
                clipped_probs = np.clip(probs_up, eps, 1 - eps)
                test_ll = float(-np.mean(y_test * np.log(clipped_probs) + (1 - y_test) * np.log(1 - clipped_probs)))
            else:
                test_acc = None
                test_brier = None
                test_ll = None

            # Save immutable provenance manifest for Phase 03 replay verification
            manifest = {
                "artifact_hash": art_hash,
                "study_id": study_id,
                "window_name": cand.window_name,
                "train_start_ms": cand.train.start_time_ms,
                "train_end_ms": cand.train.end_time_ms,  # CUTOFF
                "test_start_ms": test_win.start_time_ms,
                "test_end_ms": test_win.end_time_ms,
                "validation_accuracy": val_acc,
                "directional_accuracy": test_acc,
                "is_selected_winner": is_winner,
            }
            manifest_path = self.models_dir / f"{art_hash}.manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            results.append(
                WindowEvaluationResult(
                    window_name=cand.window_name,
                    is_eligible=True,
                    train_start_ms=cand.train.start_time_ms,
                    train_end_ms=cand.train.end_time_ms,
                    sample_count=cand.train.sample_count,
                    validation_accuracy=val_acc,
                    directional_accuracy=test_acc,
                    brier_score=test_brier,
                    log_loss=test_ll,
                    baseline_always_up_accuracy=always_up_acc,
                    baseline_majority_accuracy=majority_acc,
                    baseline_momentum_accuracy=momentum_acc,
                    artifact_path=str(art_path),
                    artifact_hash=art_hash,
                    is_selected_winner=is_winner,
                )
            )
        report = MultiWindowStudyReport(
            study_id=study_id,
            snapshot_path=str(snapshot_path),
            timeframe=timeframe,
            test_start_ms=test_win.start_time_ms,
            test_end_ms=test_win.end_time_ms,
            test_samples_count=test_win.sample_count,
            results=results,
        )

        # Save report JSON
        rep_file = self.reports_dir / f"{study_id}_study.json"
        rep_file.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

        return report
