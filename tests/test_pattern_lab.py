"""Tests for rule-based Pattern Lab, declarative rules, and sample size warnings."""

import pytest
from shootingstar.application.patterns import (
    BearishEngulfingRule,
    BullishEngulfingRule,
    HammerRule,
    PatternLabService,
    ShootingStarRule,
)
from shootingstar.domain.models import Candle


def test_shooting_star_rule_match_and_rejection():
    rule = ShootingStarRule()

    # Prior uptrend candles: 0, 1, 2
    c0 = Candle("BINANCE", "BTCUSDT", "5m", 0, 299999, 100.0, 102.0, 99.0, 101.0, 1.0, 100.0, 1, 0.5, 50.0)
    c1 = Candle("BINANCE", "BTCUSDT", "5m", 300000, 599999, 101.0, 103.0, 100.0, 102.5, 1.0, 100.0, 1, 0.5, 50.0)
    c2 = Candle("BINANCE", "BTCUSDT", "5m", 600000, 899999, 102.5, 105.0, 102.0, 104.0, 1.0, 100.0, 1, 0.5, 50.0)

    # 3: True Shooting star: open 104.2, close 104.0 (small body = 0.2), high 108.0 (upper wick = 3.8 >= 2*body), low 103.95 (lower wick = 0.05 <= 15% of 4.05 range)
    c_star = Candle("BINANCE", "BTCUSDT", "5m", 900000, 1199999, 104.2, 108.0, 103.95, 104.0, 1.0, 100.0, 1, 0.5, 50.0)

    assert rule.matches([c0, c1, c2, c_star], 3) is True

    # Negative case: big body (not shooting star)
    c_big_body = Candle("BINANCE", "BTCUSDT", "5m", 900000, 1199999, 104.2, 108.0, 103.95, 107.5, 1.0, 100.0, 1, 0.5, 50.0)
    assert rule.matches([c0, c1, c2, c_big_body], 3) is False


def test_hammer_rule_match():
    rule = HammerRule()

    # Prior downtrend: 0, 1, 2
    c0 = Candle("BINANCE", "BTCUSDT", "5m", 0, 299999, 110.0, 111.0, 108.0, 109.0, 1.0, 100.0, 1, 0.5, 50.0)
    c1 = Candle("BINANCE", "BTCUSDT", "5m", 300000, 599999, 109.0, 109.5, 106.0, 107.0, 1.0, 100.0, 1, 0.5, 50.0)
    c2 = Candle("BINANCE", "BTCUSDT", "5m", 600000, 899999, 107.0, 107.5, 104.0, 105.0, 1.0, 100.0, 1, 0.5, 50.0)

    # 3: Hammer: open 105.0, close 105.2 (body 0.2), low 101.0 (lower wick 4.0 >= 2*body), high 105.25 (upper wick 0.05)
    c_hammer = Candle("BINANCE", "BTCUSDT", "5m", 900000, 1199999, 105.0, 105.25, 101.0, 105.2, 1.0, 100.0, 1, 0.5, 50.0)

    assert rule.matches([c0, c1, c2, c_hammer], 3) is True


def test_bearish_and_bullish_engulfing():
    bear_rule = BearishEngulfingRule()
    bull_rule = BullishEngulfingRule()

    # Bearish engulfing pair
    c_green = Candle("BINANCE", "BTCUSDT", "5m", 0, 299999, 100.0, 102.0, 99.5, 101.5, 1.0, 100.0, 1, 0.5, 50.0)
    c_red_engulf = Candle("BINANCE", "BTCUSDT", "5m", 300000, 599999, 102.0, 102.5, 98.0, 99.0, 1.0, 100.0, 1, 0.5, 50.0)

    assert bear_rule.matches([c_green, c_red_engulf], 1) is True
    assert bull_rule.matches([c_green, c_red_engulf], 1) is False

    # Bullish engulfing pair
    c_red = Candle("BINANCE", "BTCUSDT", "5m", 0, 299999, 102.0, 102.5, 99.5, 100.0, 1.0, 100.0, 1, 0.5, 50.0)
    c_green_engulf = Candle("BINANCE", "BTCUSDT", "5m", 300000, 599999, 99.5, 103.5, 99.0, 103.0, 1.0, 100.0, 1, 0.5, 50.0)

    assert bull_rule.matches([c_red, c_green_engulf], 1) is True
    assert bear_rule.matches([c_red, c_green_engulf], 1) is False


def test_pattern_lab_statistical_power_warning():
    # Only 10 candles: hits will be < 30
    c0 = Candle("BINANCE", "BTCUSDT", "5m", 0, 299999, 100.0, 102.0, 99.0, 101.0, 1.0, 100.0, 1, 0.5, 50.0)
    c1 = Candle("BINANCE", "BTCUSDT", "5m", 300000, 599999, 101.0, 103.0, 100.0, 102.5, 1.0, 100.0, 1, 0.5, 50.0)
    c2 = Candle("BINANCE", "BTCUSDT", "5m", 600000, 899999, 102.5, 105.0, 102.0, 104.0, 1.0, 100.0, 1, 0.5, 50.0)
    c_star = Candle("BINANCE", "BTCUSDT", "5m", 900000, 1199999, 104.2, 108.0, 103.95, 104.0, 1.0, 100.0, 1, 0.5, 50.0)
    future_candles = [
        Candle("BINANCE", "BTCUSDT", "5m", 900000 + (j * 300000), 900000 + ((j + 1) * 300000) - 1, 103.0, 104.0, 102.0, 103.0, 1.0, 100.0, 1, 0.5, 50.0)
        for j in range(1, 10)
    ]
    candles = [c0, c1, c2, c_star] + future_candles

    lab = PatternLabService()
    report = lab.analyze_pattern(candles, ShootingStarRule(), horizon_minutes=30)

    assert report.sample_count == 1
    assert report.statistical_power_warning is True
    assert "LOW SAMPLE SIZE WARNING" in report.warning_message
    assert report.hits[0].outcome_label == "DOWN"
    assert report.hits[0].is_success is True
