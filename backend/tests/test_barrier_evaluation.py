"""Tests for Phase 03: Barrier evaluation and causal path simulation."""

from decimal import Decimal

from shootingstar.application.barrier_evaluation import (
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
