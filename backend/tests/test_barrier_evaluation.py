"""Tests for Phase 03: Barrier evaluation, path simulation, and probability estimation."""

from decimal import Decimal
import pytest

from shootingstar.application.barrier_evaluation import (
    BarrierSimulationResult,
    EmpiricalMultinomialEstimator,
    FirstTouchLabeler,
    FirstTouchOutcome,
)
from shootingstar.domain.models import Candle


def make_candle(
    open_time_ms: int,
    close_time_ms: int,
    c_open: float,
    c_high: float,
    c_low: float,
    c_close: float,
) -> Candle:
    return Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        open_time_ms=open_time_ms,
        close_time_ms=close_time_ms,
        open=c_open,
        high=c_high,
        low=c_low,
        close=c_close,
        volume=10.0,
        quote_volume=10.0 * c_close,
        trades_count=100,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=5.0 * c_close,
    )


def test_first_touch_tp_first():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49700.00")
    t0 = 1700000000000
    deadline = t0 + 1800000

    candles = [
        make_candle(t0, t0 + 299999, 50000, 50200, 49900, 50100),
        make_candle(t0 + 300000, t0 + 599999, 50100, 50600, 50050, 50550),  # touches target
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.TP_FIRST
    assert result.exit_price == target
    assert result.exit_time_ms == t0 + 599999
    assert result.gross_return_pct == Decimal("1.0")  # (50500 - 50000) / 50000 * 100 = 1.0%


def test_first_touch_sl_first():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49700.00")
    t0 = 1700000000000
    deadline = t0 + 1800000

    candles = [
        make_candle(t0, t0 + 299999, 50000, 50100, 49800, 49900),
        make_candle(t0 + 300000, t0 + 599999, 49900, 49950, 49650, 49700),  # touches stop
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.SL_FIRST
    assert result.exit_price == stop
    assert result.exit_time_ms == t0 + 599999
    assert result.gross_return_pct == Decimal("-0.6")  # (49700 - 50000) / 50000 * 100 = -0.6%


def test_post_fill_bar_both_barriers_touch_ambiguous():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49700.00")
    t0 = 1700000000000
    deadline = t0 + 1800000

    candles = [
        make_candle(t0, t0 + 299999, 50000, 50200, 49900, 50100),  # fill bar, safe
        make_candle(t0 + 300000, t0 + 599999, 50100, 50600, 49600, 50200),  # post-fill bar touches both TP and SL!
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.AMBIGUOUS
    assert result.exit_price is None
    assert result.gross_return_pct is None
    assert result.net_return_pct is None
    assert result.is_cost_gated is True
    d = result.to_dict()
    assert d["exit_price"] is None
    assert d["gross_return_pct"] is None
    assert d["net_return_pct"] is None


def test_fill_bar_tp_only_touch_unscorable():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49700.00")
    t0 = 1700000000000
    deadline = t0 + 1800000

    # Intrabar fill candle touches TP only (50600 >= target 50500)
    candles = [
        make_candle(t0, t0 + 299999, 50000, 50600, 49900, 50400),
        make_candle(t0 + 300000, t0 + 599999, 50400, 50700, 50300, 50600),
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.UNSCORABLE
    assert "intrabar fill candle" in result.note
    assert result.exit_price is None
    assert result.gross_return_pct is None
    assert result.net_return_pct is None
    assert result.is_cost_gated is True
    d = result.to_dict()
    assert d["exit_price"] is None
    assert d["gross_return_pct"] is None
    assert d["net_return_pct"] is None

def test_fill_bar_both_barriers_touch_unscorable():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49700.00")
    t0 = 1700000000000
    deadline = t0 + 1800000

    candles = [
        make_candle(t0, t0 + 299999, 50000, 50600, 49600, 50200),  # fill bar touches both TP and SL!
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.UNSCORABLE
    assert "intrabar fill candle" in result.note
    assert result.exit_price is None
    assert result.gross_return_pct is None
    assert result.net_return_pct is None
    assert result.is_cost_gated is True

def test_first_touch_timeout():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49700.00")
    t0 = 1700000000000
    deadline = t0 + 600000  # 10 minutes (2 candles)

    candles = [
        make_candle(t0, t0 + 299999, 50000, 50200, 49900, 50100),
        make_candle(t0 + 300000, t0 + 600000, 50100, 50300, 49950, 50250),  # deadline reached
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.TIMEOUT
    assert result.exit_price == Decimal("50250")
    assert result.exit_time_ms == t0 + 600000


def test_first_touch_censored():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49700.00")
    t0 = 1700000000000
    deadline = t0 + 1800000  # 30m

    # Only 5 minutes observed, neither barrier hit
    candles = [
        make_candle(t0, t0 + 299999, 50000, 50200, 49900, 50100),
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.CENSORED


def test_first_touch_unscorable_geometry():
    labeler = FirstTouchLabeler()
    # Invalid: stop >= entry
    result = labeler.evaluate_path(
        Decimal("50000"), Decimal("50500"), Decimal("50100"), 1000, 2000, []
    )
    assert result.outcome == FirstTouchOutcome.UNSCORABLE


def test_vip0_fee_and_slippage_calculation():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")  # +1.0%
    stop = Decimal("49700.00")
    t0 = 1700000000000
    deadline = t0 + 1800000

    candles = [
        make_candle(t0, t0 + 299999, 50000, 50200, 49900, 50100),  # fill candle, safe
        make_candle(t0 + 300000, t0 + 599999, 50100, 50550, 50050, 50500),  # post-fill candle touches target
    ]
    # VIP 0 fee: 10 bps, slippage: 5 bps -> total round-trip = (2*10 + 2*5) / 100 = 0.30%
    result = labeler.evaluate_path(
        entry, target, stop, t0, deadline, candles,
        fee_rate_bps=Decimal("10.0"),
        slippage_bps=Decimal("5.0"),
        has_quote_depth=True,
    )
    assert result.gross_return_pct == Decimal("1.0")
    assert result.net_return_pct == Decimal("0.7")  # 1.0% - 0.30% = 0.70%
    assert result.is_cost_gated is False


def test_empirical_multinomial_estimator_gating():
    estimator = EmpiricalMultinomialEstimator()
    # Only 10 samples -> must gate with nulls
    outcomes = [FirstTouchOutcome.TP_FIRST] * 6 + [FirstTouchOutcome.SL_FIRST] * 4
    estimate = estimator.estimate(outcomes, min_samples=30)

    assert estimate.is_calibrated is False
    assert estimate.p_tp is None
    assert estimate.p_sl is None
    assert estimate.p_timeout is None
    assert "Insufficient sample size" in (estimate.gating_reason or "")


def test_empirical_multinomial_estimator_sufficient_samples():
    estimator = EmpiricalMultinomialEstimator()
    # 30 samples: 15 TP, 9 SL, 6 TIMEOUT
    outcomes = (
        [FirstTouchOutcome.TP_FIRST] * 15
        + [FirstTouchOutcome.SL_FIRST] * 9
        + [FirstTouchOutcome.TIMEOUT] * 6
    )
    estimate = estimator.estimate(outcomes, min_samples=30, alpha=1.0)

    assert estimate.is_calibrated is True
    assert estimate.gating_reason is None
    assert estimate.sample_size == 30
    # smoothed: (15+1)/(30+3) = 16/33 ~= 0.4848
    # (9+1)/33 = 10/33 ~= 0.3030
    # (6+1)/33 = 7/33 ~= 0.2121
    assert estimate.p_tp == 0.4848
    assert estimate.p_sl == 0.3030
    assert estimate.p_timeout == 0.2121
    assert round(estimate.p_tp + estimate.p_sl + estimate.p_timeout, 2) == 1.00


def test_empirical_estimator_credible_intervals():
    estimator = EmpiricalMultinomialEstimator()
    outcomes = (
        [FirstTouchOutcome.TP_FIRST] * 20
        + [FirstTouchOutcome.SL_FIRST] * 10
        + [FirstTouchOutcome.TIMEOUT] * 5
    )
    estimate = estimator.estimate(outcomes, min_samples=30, alpha=1.0)
    assert estimate.is_calibrated is True
    assert estimate.credible_intervals is not None
    assert "p_tp" in estimate.credible_intervals
    assert "p_sl" in estimate.credible_intervals
    assert "p_timeout" in estimate.credible_intervals

    tp_low, tp_high = estimate.credible_intervals["p_tp"]
    assert 0.0 < tp_low < estimate.p_tp < tp_high < 1.0
    # Width must be sensible
    assert (tp_high - tp_low) < 0.35


def test_barrier_artifact_save_load_roundtrip(tmp_path):
    from shootingstar.application.barrier_evaluation import (
        BarrierArtifactManager,
        BarrierModelArtifact,
    )

    artifact = BarrierModelArtifact(
        artifact_hash="test1234abcd",
        strategy_version="v1-support-reclaim-30m",
        created_at_utc="2026-10-10T00:00:00Z",
        train_cutoff_ms=1700000000000,
        sample_size=50,
        alpha_smoothing=1.0,
        p_tp=0.50,
        p_sl=0.30,
        p_timeout=0.20,
        credible_intervals={"p_tp": (0.40, 0.60), "p_sl": (0.22, 0.38), "p_timeout": (0.12, 0.28)},
    )

    saved_path = BarrierArtifactManager.save_artifact(artifact, tmp_path)
    assert saved_path.exists()

    loaded = BarrierArtifactManager.load_artifact(saved_path)
    assert loaded.artifact_hash == artifact.artifact_hash
    assert loaded.sample_size == 50
    assert loaded.credible_intervals["p_tp"] == (0.40, 0.60)
    assert loaded.is_approved is False


def test_multiclass_metrics_and_approval_gates(tmp_path):
    from shootingstar.application.barrier_evaluation import (
        BarrierArtifactManager,
        BarrierModelArtifact,
    )

    artifact = BarrierModelArtifact(
        artifact_hash="gate_test_hash",
        strategy_version="v1-support-reclaim-30m",
        created_at_utc="2026-10-10T00:00:00Z",
        train_cutoff_ms=1700000000000,
        sample_size=60,
        alpha_smoothing=1.0,
        p_tp=0.60,
        p_sl=0.25,
        p_timeout=0.15,
        credible_intervals={"p_tp": (0.50, 0.70), "p_sl": (0.18, 0.32), "p_timeout": (0.09, 0.22)},
    )
    art_path = BarrierArtifactManager.save_artifact(artifact, tmp_path)

    # Test compute multiclass metrics
    test_outcomes = [FirstTouchOutcome.TP_FIRST] * 12 + [FirstTouchOutcome.SL_FIRST] * 4 + [FirstTouchOutcome.TIMEOUT] * 2
    metrics = BarrierArtifactManager.compute_multiclass_metrics(
        p_tp=artifact.p_tp,
        p_sl=artifact.p_sl,
        p_timeout=artifact.p_timeout,
        outcomes=test_outcomes,
        eval_start_ms=1700000001000,  # strictly > train_cutoff_ms
    )
    assert metrics["test_samples"] == 18.0
    assert metrics["brier_score"] < 0.667  # beats uniform

    # Passing gates
    approved = BarrierArtifactManager.approve_artifact(art_path, metrics, approver="test_admin")
    assert approved.is_approved is True
    assert approved.approved_by == "test_admin"
    assert "APPROVED" in (approved.approval_verdict or "")

    # Failing Gate 4: bad brier score
    bad_metrics = {"test_samples": 20.0, "brier_score": 0.85, "log_loss": 1.5, "eval_start_ms": 1700000001000}
    with pytest.raises(ValueError, match="Approval rejected"):
        BarrierArtifactManager.approve_artifact(art_path, bad_metrics, approver="bad_admin")

    # Failing Gate 5: temporal leakage (eval_start_ms <= train_cutoff_ms)
    leak_metrics = {"test_samples": 20.0, "brier_score": 0.50, "log_loss": 0.8, "eval_start_ms": 1700000000000}
    with pytest.raises(ValueError, match="Gate 5 failed: Evaluation start time"):
        BarrierArtifactManager.approve_artifact(art_path, leak_metrics, approver="leak_admin")


def test_cli_barrier_research_evaluate_approve_lifecycle(tmp_path):
    import json
    from shootingstar.adapters.storage import SnapshotStorage
    from shootingstar.cli.main import main

    storage = SnapshotStorage(snapshots_dir=tmp_path / "snapshots")
    base_time = 1700000000000
    import math
    candles = []
    for i in range(350):
        open_t = base_time + (i * 300000)
        close_t = open_t + 299999
        osc = math.sin(i / 6.0) * 800.0
        price_c = 50000.0 + osc
        c_open = price_c - 30.0
        c_close = price_c
        c_high = max(c_open, c_close) + 150.0
        c_low = min(c_open, c_close) - 150.0
        candles.append(make_candle(open_t, close_t, c_open, c_high, c_low, c_close))
    snap_path, snap_sha = storage.save_snapshot(candles, "BINANCE", "BTCUSDT", "5m")
    out_dir = tmp_path / "models"

    # 1. CLI: research-entry-strategy
    ret_code = main([
        "research-entry-strategy",
        "--snapshot", str(snap_path),
        "--out-dir", str(out_dir),
        "--min-samples", "1",
        "--train-ratio", "0.70",
    ])
    assert ret_code == 0

    art_files = list(out_dir.glob("barrier_*.manifest.json"))
    assert len(art_files) == 1
    art_path = art_files[0]

    # 2. CLI: evaluate-entry-strategy (strictly OOS test candles)
    ret_code = main([
        "evaluate-entry-strategy",
        "--artifact", str(art_path),
        "--snapshot", str(snap_path),
        "--out-dir", str(out_dir),
    ])
    assert ret_code == 0

    report_files = list(out_dir.glob("eval_*.json"))
    assert len(report_files) == 1
    report_path = report_files[0]
    report_data = json.loads(report_path.read_text(encoding="utf-8"))
    assert "brier_score" in report_data
    assert report_data["eval_start_ms"] is not None

    # 3. CLI: approve-entry-artifact -> run directly on unmodified report from evaluation
    ret_code_rejected = main([
        "approve-entry-artifact",
        "--artifact", str(art_path),
        "--evaluation-report", str(report_path),
        "--approver", "lead_quant",
    ])
    # Must reject with code 1 because gates strictly enforce min samples and CI widths
    assert ret_code_rejected == 1

    # Verify artifact is persisted with rejection audit trail and remains unapproved
    final_art = json.loads(art_path.read_text(encoding="utf-8"))
    assert final_art["is_approved"] is False
    assert final_art["approved_by"] == "lead_quant"
    assert "REJECTED" in (final_art["approval_verdict"] or "")
    assert "Gate 1 failed" in final_art["approval_verdict"]


def test_no_post_deadline_leakage():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49500.00")
    t0 = 1700000000000
    deadline = t0 + 1800000  # 30 minutes

    # 6 candles of 5m spanning exactly [t0, t0 + 1800000], none touches TP or SL
    candles = []
    for i in range(6):
        c_open_t = t0 + (i * 300000)
        c_close_t = c_open_t + 299999
        candles.append(make_candle(c_open_t, c_close_t, 50000, 50200, 49800, 50100))

    # 7th candle opens strictly AFTER deadline and reaches 50800 (above target)
    post_open_t = t0 + 1800000
    post_close_t = post_open_t + 299999
    candles.append(make_candle(post_open_t, post_close_t, 50100, 50800, 50000, 50700))

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    # Must resolve at deadline as TIMEOUT, strictly ignoring the post-deadline breach
    assert result.outcome == FirstTouchOutcome.TIMEOUT
    assert result.outcome != FirstTouchOutcome.TP_FIRST
    assert result.exit_time_ms <= deadline


def test_straddling_candle_no_barrier_timeout():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49500.00")
    t0 = 1700000000000
    # 25 minutes + 500ms -> deadline falls strictly inside the 6th candle (1500000 to 1800000)
    deadline = t0 + 1500500

    candles = [
        make_candle(t0, t0 + 299999, 50000, 50200, 49800, 50100),
        make_candle(t0 + 300000, t0 + 599999, 50100, 50250, 49900, 50150),
        make_candle(t0 + 600000, t0 + 899999, 50150, 50200, 49950, 50050),
        make_candle(t0 + 900000, t0 + 1199999, 50050, 50300, 49850, 50100),
        make_candle(t0 + 1200000, t0 + 1499999, 50100, 50200, 49900, 50000),
        # 6th candle opens at 1500000 (< deadline) and closes at 1799999 (> deadline)
        # Neither TP (50500) nor SL (49500) touched throughout the candle
        make_candle(t0 + 1500000, t0 + 1799999, 50000, 50300, 49800, 50100),
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.TIMEOUT
    assert result.exit_time_ms == deadline
    assert result.exit_price is None
    assert result.gross_return_pct is None
    assert result.net_return_pct is None
    assert result.is_cost_gated is True
    assert "no invented exit price/fee" in result.note
    d = result.to_dict()
    assert d["exit_price"] is None
    assert d["gross_return_pct"] is None
    assert d["net_return_pct"] is None

def test_straddling_candle_barrier_touch_unscorable():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49500.00")
    t0 = 1700000000000
    deadline = t0 + 1500500

    candles = [
        make_candle(t0, t0 + 299999, 50000, 50200, 49800, 50100),
        make_candle(t0 + 300000, t0 + 599999, 50100, 50250, 49900, 50150),
        make_candle(t0 + 600000, t0 + 899999, 50150, 50200, 49950, 50050),
        make_candle(t0 + 900000, t0 + 1199999, 50050, 50300, 49850, 50100),
        make_candle(t0 + 1200000, t0 + 1499999, 50100, 50200, 49900, 50000),
        # 6th candle straddles deadline and touches TP (50500) -> unscorable without intrabar ticks
        make_candle(t0 + 1500000, t0 + 1799999, 50000, 50600, 49800, 50550),
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.UNSCORABLE
    assert "straddles deadline" in result.note
    assert result.exit_price is None
    assert result.gross_return_pct is None
    assert result.net_return_pct is None
    assert result.is_cost_gated is True
    d = result.to_dict()
    assert d["exit_price"] is None
    assert d["gross_return_pct"] is None
    assert d["net_return_pct"] is None


def test_straddling_candle_both_barriers_touch_unscorable():
    labeler = FirstTouchLabeler()
    entry = Decimal("50000.00")
    target = Decimal("50500.00")
    stop = Decimal("49500.00")
    t0 = 1700000000000
    deadline = t0 + 1500500

    candles = [
        make_candle(t0, t0 + 299999, 50000, 50200, 49800, 50100),
        make_candle(t0 + 300000, t0 + 599999, 50100, 50250, 49900, 50150),
        make_candle(t0 + 600000, t0 + 899999, 50150, 50200, 49950, 50050),
        make_candle(t0 + 900000, t0 + 1199999, 50050, 50300, 49850, 50100),
        make_candle(t0 + 1200000, t0 + 1499999, 50100, 50200, 49900, 50000),
        # 6th candle straddles deadline and touches BOTH TP (50600 >= 50500) and SL (49400 <= 49500)
        # Must be UNSCORABLE (not AMBIGUOUS) because touches could have happened post-deadline
        make_candle(t0 + 1500000, t0 + 1799999, 50000, 50600, 49400, 50100),
    ]

    result = labeler.evaluate_path(entry, target, stop, t0, deadline, candles)
    assert result.outcome == FirstTouchOutcome.UNSCORABLE
    assert "straddles deadline" in result.note
    assert result.exit_price is None
    assert result.gross_return_pct is None
    assert result.net_return_pct is None
    d = result.to_dict()
    assert d["exit_price"] is None
    assert d["gross_return_pct"] is None
    assert d["net_return_pct"] is None
def test_straddling_candle_false_fill_rejected():
    p_entry = Decimal("49200.00")
    t0 = 1700000000000
    deadline = t0 + 1500500

    # Forward candles where candles 1-5 never touch 49200 (low >= 49500)
    forward = [
        make_candle(t0, t0 + 299999, 50000, 50200, 49800, 50100),
        make_candle(t0 + 300000, t0 + 599999, 50100, 50250, 49900, 50150),
        make_candle(t0 + 600000, t0 + 899999, 50150, 50200, 49950, 50050),
        make_candle(t0 + 900000, t0 + 1199999, 50050, 50300, 49850, 50100),
        make_candle(t0 + 1200000, t0 + 1499999, 50100, 50200, 49900, 50000),
        # 6th candle straddles deadline and reaches 49100 (which touches p_entry), but might be post-deadline!
        make_candle(t0 + 1500000, t0 + 1799999, 50000, 50200, 49100, 49300),
    ]

    # Fill discovery restricted to fully completed in-horizon candles
    in_horizon = [c for c in forward if (c.close_time_ms + 1) <= deadline]
    assert len(in_horizon) == 5
    fill_idx = next(
        (idx for idx, c in enumerate(in_horizon) if Decimal(str(c.low)) <= p_entry <= Decimal(str(c.high))),
        None,
    )
    # Must be None - false fill on straddling bar strictly rejected!
    assert fill_idx is None
