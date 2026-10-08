"""Evaluation metrics, calibration curves, and honest research report generation."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, log_loss, precision_score, recall_score

from shootingstar.application.baselines import (
    AlwaysDownBaseline,
    AlwaysUpBaseline,
    BaselineEvaluator,
    BaselineMetrics,
    MajorityClassBaseline,
    SimpleMomentumBaseline,
)
from shootingstar.application.modeling import CalibratedLogisticRegressionModel


@dataclass(frozen=True)
class CalibrationBin:
    bin_index: int
    bin_range: str
    sample_count: int
    mean_predicted_prob: float
    empirical_frequency: float


@dataclass(frozen=True)
class DirectionalMetrics:
    sample_count: int
    up_count: int
    down_count: int
    accuracy: float
    precision_up: float
    recall_up: float
    f1_up: float
    precision_down: float
    recall_down: float
    f1_down: float
    brier_score: float
    log_loss: float


@dataclass(frozen=True)
class EvaluationReport:
    experiment_id: str
    snapshot_sha256: str
    symbol: str
    timeframe: str
    horizon_minutes: int
    test_start_time_ms: int
    test_end_time_ms: int
    directional_metrics: DirectionalMetrics
    calibration_bins: List[CalibrationBin]
    baseline_comparisons: List[Dict[str, Any]]
    cost_adjusted_fields_status: Dict[str, str]  # Explicit UNAVAILABLE_PENDING_SLIPPAGE_METHOD status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "snapshot_sha256": self.snapshot_sha256,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "horizon_minutes": self.horizon_minutes,
            "test_start_time_ms": self.test_start_time_ms,
            "test_end_time_ms": self.test_end_time_ms,
            "directional_metrics": asdict(self.directional_metrics),
            "calibration_bins": [asdict(b) for b in self.calibration_bins],
            "baseline_comparisons": self.baseline_comparisons,
            "cost_adjusted_fields_status": self.cost_adjusted_fields_status,
        }

    def to_markdown(self) -> str:
        d = self.directional_metrics
        lines = [
            f"# Research Report: {self.experiment_id}",
            "",
            "## 1. Setup & Horizon",
            f"- **Symbol:** {self.symbol}",
            f"- **Timeframe:** {self.timeframe}",
            f"- **Horizon:** {self.horizon_minutes} minutes forward",
            f"- **Snapshot SHA-256:** `{self.snapshot_sha256}`",
            f"- **Test Window:** {self.test_start_time_ms} to {self.test_end_time_ms} ({d.sample_count} samples)",
            f"- **Class Distribution:** UP={d.up_count} ({d.up_count/d.sample_count*100:.1f}%), DOWN={d.down_count} ({d.down_count/d.sample_count*100:.1f}%)",
            "",
            "## 2. Directional Performance (Out-of-Sample Test)",
            f"- **Accuracy:** {d.accuracy*100:.2f}%",
            f"- **Precision (UP):** {d.precision_up*100:.2f}% | **Recall (UP):** {d.recall_up*100:.2f}% | **F1 (UP):** {d.f1_up*100:.2f}%",
            f"- **Precision (DOWN):** {d.precision_down*100:.2f}% | **Recall (DOWN):** {d.recall_down*100:.2f}% | **F1 (DOWN):** {d.f1_down*100:.2f}%",
            f"- **Brier Score:** {d.brier_score:.4f} (lower is better, 0.25 is random coin flip)",
            f"- **Log Loss:** {d.log_loss:.4f}",
            "",
            "## 3. Probability Calibration Bins",
            "| Bin | Range | Samples | Mean Pred Prob | Empirical Observed UP |",
            "|---|---|---|---|---|",
        ]
        for b in self.calibration_bins:
            lines.append(f"| {b.bin_index} | {b.bin_range} | {b.sample_count} | {b.mean_predicted_prob*100:.1f}% | {b.empirical_frequency*100:.1f}% |")

        lines.extend([
            "",
            "## 4. Baseline Comparison",
            "| Model | Accuracy | Precision UP | Recall UP | Spot Return/Signal | Spot Cumulative |",
            "|---|---|---|---|---|---|",
        ])
        for b in self.baseline_comparisons:
            lines.append(
                f"| {b['name']} | {b['accuracy']*100:.2f}% | {b['precision_up']*100:.2f}% | {b['recall_up']*100:.2f}% | {b['spot_mean_return_per_signal']*100:.4f}% | {b['spot_cumulative_return']*100:.2f}% |"
            )

        lines.extend([
            "",
            "## 5. Cost-Adjusted Status & Policy Gates",
            "> **CRITICAL INVARIANT:** No arbitrary zero slippage was applied.",
            "",
        ])
        for field, status in self.cost_adjusted_fields_status.items():
            lines.append(f"- **{field}:** `{status}`")

        return "\n".join(lines)


class EvaluationReportGenerator:
    """Generates out-of-sample test reports with honest probability calibration."""

    @staticmethod
    def generate_report(
        model: CalibratedLogisticRegressionModel,
        X_test: np.ndarray,
        y_test: np.ndarray,
        returns_test: np.ndarray,
        experiment_id: str,
        snapshot_sha256: str,
        symbol: str,
        timeframe: str,
        horizon_minutes: int,
        test_start_time_ms: int,
        test_end_time_ms: int,
    ) -> EvaluationReport:
        proba = model.predict_proba(X_test)
        p_up = proba[:, 1]
        preds = np.where(p_up >= 0.5, 1, 0)

        n = len(y_test)
        up_count = int(np.sum(y_test == 1))
        down_count = int(np.sum(y_test == 0))

        acc = float(accuracy_score(y_test, preds))
        p_up_score = float(precision_score(y_test, preds, pos_label=1, zero_division=0))
        r_up_score = float(recall_score(y_test, preds, pos_label=1, zero_division=0))
        f1_up_score = float(f1_score(y_test, preds, pos_label=1, zero_division=0))

        p_down_score = float(precision_score(y_test, preds, pos_label=0, zero_division=0))
        r_down_score = float(recall_score(y_test, preds, pos_label=0, zero_division=0))
        f1_down_score = float(f1_score(y_test, preds, pos_label=0, zero_division=0))

        brier = float(brier_score_loss(y_test, p_up))
        ll = float(log_loss(y_test, proba))

        dir_metrics = DirectionalMetrics(
            sample_count=n,
            up_count=up_count,
            down_count=down_count,
            accuracy=acc,
            precision_up=p_up_score,
            recall_up=r_up_score,
            f1_up=f1_up_score,
            precision_down=p_down_score,
            recall_down=r_down_score,
            f1_down=f1_down_score,
            brier_score=brier,
            log_loss=ll,
        )

        # 5 Probability Calibration Bins
        bin_edges = [0.0, 0.40, 0.48, 0.52, 0.60, 1.0]
        calib_bins: List[CalibrationBin] = []
        for i in range(len(bin_edges) - 1):
            low, high = bin_edges[i], bin_edges[i + 1]
            mask = (p_up >= low) & (p_up < high) if i < len(bin_edges) - 2 else (p_up >= low) & (p_up <= high)
            count = int(np.sum(mask))
            if count > 0:
                mean_prob = float(np.mean(p_up[mask]))
                emp_freq = float(np.mean(y_test[mask] == 1))
            else:
                mean_prob = float((low + high) / 2.0)
                emp_freq = 0.0

            calib_bins.append(
                CalibrationBin(
                    bin_index=i + 1,
                    bin_range=f"[{low:.2f}, {high:.2f}]",
                    sample_count=count,
                    mean_predicted_prob=mean_prob,
                    empirical_frequency=emp_freq,
                )
            )

        # Baselines
        baselines_list = [
            AlwaysUpBaseline(),
            AlwaysDownBaseline(),
            MajorityClassBaseline(),
            SimpleMomentumBaseline(),
        ]
        # Train majority class on train set if available, else predict mode
        baseline_comparisons: List[Dict[str, Any]] = []

        # Include Logistic Regression in comparison table
        spot_lr_returns = np.where(preds == 1, returns_test, 0.0)
        baseline_comparisons.append({
            "name": "Logistic_Regression (Calibrated)",
            "accuracy": acc,
            "precision_up": p_up_score,
            "recall_up": r_up_score,
            "spot_mean_return_per_signal": float(np.mean(spot_lr_returns)),
            "spot_cumulative_return": float(np.sum(spot_lr_returns)),
        })

        for b in baselines_list:
            b.fit(y_test)
            res = BaselineEvaluator.evaluate(b, X_test, y_test, returns_test)
            baseline_comparisons.append({
                "name": res.name,
                "accuracy": res.accuracy,
                "precision_up": res.precision_up,
                "recall_up": res.recall_up,
                "spot_mean_return_per_signal": res.spot_mean_return_per_signal,
                "spot_cumulative_return": res.spot_cumulative_return,
            })

        cost_status = {
            "Action Policy (Three-Class UP/DOWN/NO_TRADE)": "UNAVAILABLE_PENDING_SLIPPAGE_METHOD",
            "Net Expectancy After Costs": "UNAVAILABLE_PENDING_SLIPPAGE_METHOD",
            "Win Rate After Fee & Slippage": "UNAVAILABLE_PENDING_SLIPPAGE_METHOD",
            "Maximum Drawdown After Costs": "UNAVAILABLE_PENDING_SLIPPAGE_METHOD",
            "Post-Cost Regime Breakdown": "UNAVAILABLE_PENDING_SLIPPAGE_METHOD",
        }

        return EvaluationReport(
            experiment_id=experiment_id,
            snapshot_sha256=snapshot_sha256,
            symbol=symbol,
            timeframe=timeframe,
            horizon_minutes=horizon_minutes,
            test_start_time_ms=test_start_time_ms,
            test_end_time_ms=test_end_time_ms,
            directional_metrics=dir_metrics,
            calibration_bins=calib_bins,
            baseline_comparisons=baseline_comparisons,
            cost_adjusted_fields_status=cost_status,
        )
