"""Behavioral and invariant unit tests for 30m fast entry strategy and domain models."""

import pytest
from decimal import Decimal
from shootingstar.domain.models import Candle
from shootingstar.domain.trade_plan import (
    BarrierProbability,
    CandidatePlan,
    CandidateState,
    ConfirmationRule,
    DecisionReason,
    EntryZone,
    ExecutionMode,
    InvalidationRule,
    ObservationDecision,
    PayoffExpectancyModel,
    RiskConfig,
    SymbolFilters,
)
from shootingstar.application.entry_strategy import EntryStrategyEngine


@pytest.fixture
def btc_symbol_filters() -> SymbolFilters:
    return SymbolFilters(
        symbol="BTCUSDT",
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.00001"),
        min_notional=Decimal("5.0"),
        min_qty=Decimal("0.00001"),
    )


@pytest.fixture
def sample_risk_config() -> RiskConfig:
    return RiskConfig(
        max_notional_usdt=Decimal("1000.00"),
        max_planned_loss_usdt=Decimal("50.00"),
        fee_rate_bps=Decimal("10.0"),       # 0.10%
        slippage_bps=Decimal("5.0"),        # 0.05%
        max_wait_duration_ms=1_800_000,     # 30m
        max_entry_deviation_pct=Decimal("0.002"),  # 0.2%
        freshness_tolerance_ms=120_000,
        max_event_lag_ms=5_000,
        cost_model_source="vip0-evidence-v1",
    )


def make_candle(
    index: int,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    base_time_ms: int = 1_700_000_000_000,
    interval_ms: int = 60_000,
    observed_latency_ms: int = 500,
) -> Candle:
    open_t = base_time_ms + index * interval_ms
    close_t = open_t + interval_ms
    return Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=open_t,
        close_time_ms=close_t,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=10.0,
        quote_volume=10.0 * close_p,
        trades_count=100,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=5.0 * close_p,
        observed_ingested_at_ms=close_t + observed_latency_ms,
    )


def test_symbol_filters_non_power_of_ten_increments():
    # Test filters with non-power-of-ten increments (e.g. tick 0.05, step 0.005)
    filters = SymbolFilters(
        symbol="TESTUSDT",
        tick_size=Decimal("0.05"),
        step_size=Decimal("0.005"),
        min_notional=Decimal("10.0"),
        min_qty=Decimal("0.005"),
    )

    # Price 100.03 rounded up or half-up to multiple of 0.05 -> 100.05
    assert filters.quantize_price(Decimal("100.03")) == Decimal("100.05")
    # Price 100.02 rounded down to multiple of 0.05 -> 100.00
    assert filters.quantize_price(Decimal("100.02")) == Decimal("100.00")

    # Quantity strictly floored to multiple of 0.005
    # 0.1249 -> 0.120
    assert filters.quantize_quantity_floor(Decimal("0.1249")) == Decimal("0.120")
    # 0.1251 -> 0.125
    assert filters.quantize_quantity_floor(Decimal("0.1251")) == Decimal("0.125")


def test_domain_model_invariants(btc_symbol_filters, sample_risk_config):
    entry_zone = EntryZone(min_price=Decimal("90000"), max_price=Decimal("90100"), proposed_entry=Decimal("90050"))
    confirmation = ConfirmationRule(support_level=Decimal("90000"), reclaim_level=Decimal("90050"))
    invalidation = InvalidationRule(invalidation_price=Decimal("89500"), buffer_percent=Decimal("0.002"))

    plan = CandidatePlan(
        candidate_id="cand_1",
        strategy_version="v1",
        rule_config_hash="abc",
        decision_time_ms=1_000_000,
        available_cutoff_ms=1_000_000,
        entry_zone=entry_zone,
        confirmation=confirmation,
        invalidation=invalidation,
        stop_price=Decimal("89500"),
        target_price=Decimal("91000"),
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
        wait_expires_at_ms=2_000_000,
    )
    assert plan.proposed_entry == Decimal("90050")

    with pytest.raises(ValueError, match="Barrier order invariant violated"):
        CandidatePlan(
            candidate_id="cand_bad",
            strategy_version="v1",
            rule_config_hash="abc",
            decision_time_ms=1_000_000,
            available_cutoff_ms=1_000_000,
            entry_zone=entry_zone,
            confirmation=confirmation,
            invalidation=invalidation,
            stop_price=Decimal("90100"),
            target_price=Decimal("92000"),
            risk_config=sample_risk_config,
            symbol_filters=btc_symbol_filters,
            wait_expires_at_ms=2_000_000,
        )


def test_floored_quantity_never_exceeds_risk(btc_symbol_filters, sample_risk_config):
    entry_zone = EntryZone(min_price=Decimal("90000"), max_price=Decimal("90100"), proposed_entry=Decimal("90000"))
    confirmation = ConfirmationRule(support_level=Decimal("90000"), reclaim_level=Decimal("90000"))
    invalidation = InvalidationRule(invalidation_price=Decimal("89000"), buffer_percent=Decimal("0.002"))

    plan = CandidatePlan(
        candidate_id="cand_1",
        strategy_version="v1",
        rule_config_hash="abc",
        decision_time_ms=1_000_000,
        available_cutoff_ms=1_000_000,
        entry_zone=entry_zone,
        confirmation=confirmation,
        invalidation=invalidation,
        stop_price=Decimal("89000"),
        target_price=Decimal("92000"),
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
        wait_expires_at_ms=2_000_000,
    )

    qty = plan.compute_planned_quantity()
    assert qty > Decimal("0")
    assert (qty * plan.proposed_entry) <= sample_risk_config.max_notional_usdt
    planned_loss = plan.compute_planned_loss_usdt(qty)
    assert planned_loss <= sample_risk_config.max_planned_loss_usdt


def test_create_candidate_locks_barriers_and_advances_without_drift(btc_symbol_filters, sample_risk_config):
    engine = EntryStrategyEngine(lookback_bars=10)
    base_t = 1_700_000_000_000

    candles = []
    for i in range(11):
        low = 89500.0 if i == 4 else 89800.0
        high = 92500.0 if i == 2 else 90500.0
        candles.append(make_candle(i, 90000.0, high, low, 90200.0, base_time_ms=base_t))

    cutoff = candles[-1].close_time_ms + 1000
    plan, decision, reasons = engine.create_candidate(
        candles=candles,
        decision_time_ms=cutoff,
        available_cutoff_ms=cutoff,
        symbol_filters=btc_symbol_filters,
        risk_config=sample_risk_config,
    )

    assert decision == ObservationDecision.WAIT_CONFIRMATION
    assert plan is not None
    assert plan.stop_price < plan.proposed_entry < plan.target_price
    initial_deadline = plan.wait_expires_at_ms
    initial_stop = plan.stop_price

    new_candle = make_candle(11, 90200.0, 90300.0, 89900.0, 90150.0, base_time_ms=base_t)
    adv_plan, adv_decision, adv_reasons = engine.advance_candidate(
        locked_plan=plan,
        new_candles=[new_candle],
        current_time_ms=new_candle.close_time_ms + 1000,
    )
    assert adv_decision == ObservationDecision.WAIT_CONFIRMATION
    assert adv_plan.wait_expires_at_ms == initial_deadline
    assert adv_plan.stop_price == initial_stop


def test_invalidation_precedence_on_advance(btc_symbol_filters, sample_risk_config):
    engine = EntryStrategyEngine(lookback_bars=10)
    base_t = 1_700_000_000_000

    candles = []
    for i in range(11):
        low = 89500.0 if i == 4 else 89800.0
        high = 92500.0 if i == 2 else 90500.0
        candles.append(make_candle(i, 90000.0, high, low, 90200.0, base_time_ms=base_t))

    cutoff = candles[-1].close_time_ms + 1000
    plan, _, _ = engine.create_candidate(
        candles=candles,
        decision_time_ms=cutoff,
        available_cutoff_ms=cutoff,
        symbol_filters=btc_symbol_filters,
        risk_config=sample_risk_config,
    )

    # Invalidation candle: low breaches stop_price (e.g. 89200 <= 89321) even if close reclaims
    breach_candle = make_candle(11, 90200.0, 90400.0, 89200.0, 90300.0, base_time_ms=base_t)
    adv_plan, adv_decision, adv_reasons = engine.advance_candidate(
        locked_plan=plan,
        new_candles=[breach_candle],
        current_time_ms=breach_candle.close_time_ms + 1000,
    )

    assert adv_decision == ObservationDecision.SKIP
    assert DecisionReason.INVALIDATED in adv_reasons
    assert adv_plan.candidate_state == CandidateState.INVALIDATED


def test_confirmation_and_unverified_vs_buy_eligible(btc_symbol_filters, sample_risk_config):
    engine = EntryStrategyEngine(lookback_bars=10)
    base_t = 1_700_000_000_000

    candles = []
    for i in range(11):
        low = 89500.0 if i == 4 else 89800.0
        high = 92500.0 if i == 2 else 90500.0
        candles.append(make_candle(i, 90000.0, high, low, 90200.0, base_time_ms=base_t))

    cutoff = candles[-1].close_time_ms + 1000
    plan, _, _ = engine.create_candidate(
        candles=candles,
        decision_time_ms=cutoff,
        available_cutoff_ms=cutoff,
        symbol_filters=btc_symbol_filters,
        risk_config=sample_risk_config,
    )

    # Confirmation candle: low touches support zone (89550), close reclaims (90200)
    confirm_candle = make_candle(11, 89900.0, 90400.0, 89550.0, 90200.0, base_time_ms=base_t)

    # 1. Without probability and payoff model -> WATCH_ONLY
    w_plan, w_decision, w_reasons = engine.advance_candidate(
        locked_plan=plan,
        new_candles=[confirm_candle],
        current_time_ms=confirm_candle.close_time_ms + 1000,
        probability=None,
        cost_model_approved=False,
    )
    assert w_decision == ObservationDecision.WATCH_ONLY
    assert DecisionReason.COST_UNVERIFIED in w_reasons
    assert DecisionReason.PROBABILITY_UNVERIFIED in w_reasons

    # 2. With verified probability & approved payoff model -> BUY_ELIGIBLE
    valid_prob = BarrierProbability(
        tp_first=0.60,
        sl_first=0.25,
        timeout=0.15,
        calibration_status="CALIBRATED",
        sample_count=200,
        artifact_version="multinomial-v1",
    )
    approved_model = PayoffExpectancyModel(
        model_version="cost-v1",
        is_approved=True,
        expected_tp_slippage_bps=Decimal("2"),
        expected_sl_slippage_bps=Decimal("5"),
        expected_timeout_net_return_bps=Decimal("0"),
    )
    b_plan, b_decision, b_reasons = engine.advance_candidate(
        locked_plan=plan,
        new_candles=[confirm_candle],
        current_time_ms=confirm_candle.close_time_ms + 1000,
        probability=valid_prob,
        payoff_model=approved_model,
        cost_model_approved=True,
    )
    assert b_decision == ObservationDecision.BUY_ELIGIBLE
    assert DecisionReason.SETUP_VALID in b_reasons
    assert b_plan.candidate_state == CandidateState.ELIGIBLE


def test_entry_deviation_and_retroactive_sl_breach(btc_symbol_filters, sample_risk_config):
    engine = EntryStrategyEngine()
    entry_zone = EntryZone(min_price=Decimal("90000"), max_price=Decimal("90100"), proposed_entry=Decimal("90000"))
    confirmation = ConfirmationRule(support_level=Decimal("90000"), reclaim_level=Decimal("90000"))
    invalidation = InvalidationRule(invalidation_price=Decimal("89500"), buffer_percent=Decimal("0.002"))

    plan = CandidatePlan(
        candidate_id="cand_1",
        strategy_version="v1",
        rule_config_hash="abc",
        decision_time_ms=1_000_000,
        available_cutoff_ms=1_000_000,
        entry_zone=entry_zone,
        confirmation=confirmation,
        invalidation=invalidation,
        stop_price=Decimal("89500"),
        target_price=Decimal("92000"),
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
        wait_expires_at_ms=2_000_000,
    )

    obs = engine.validate_and_record_entry(
        plan=plan,
        actual_price=Decimal("90900"),
        actual_quantity=Decimal("0.005"),
        actual_entry_time_ms=1_050_000,
        receipt_time_ms=1_060_000,
        mode=ExecutionMode.MANUAL_REPORTED,
        recent_low_since_entry=Decimal("89400"),
    )
    assert obs.is_off_plan is True
    assert obs.reconciled_sl_breach_detected is True
    assert obs.is_risk_breach is True
