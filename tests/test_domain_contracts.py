"""Tests for domain contracts, temporal availability, and boundary conditions.

Zero network and zero database dependencies.
"""

import pytest
from shootingstar.domain.exceptions import InvalidCandleError
from shootingstar.domain.models import Candle, Timeframe, Venue, Symbol
from shootingstar.application.contracts import QualityInspectorService


def test_valid_candle_creation_and_temporal_separation():
    candle = Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=1700000000000,
        close_time_ms=1700000059999,
        open=50000.0,
        high=50100.0,
        low=49950.0,
        close=50050.0,
        volume=12.5,
        quote_volume=625000.0,
        trades_count=150,
        taker_buy_base_volume=6.0,
        taker_buy_quote_volume=300000.0,
        observed_ingested_at_ms=None,
    )
    assert candle.key == ("BINANCE", "BTCUSDT", "1m", 1700000000000)

    # 1. Period closure checks interval end strictly
    assert candle.is_period_closed(1700000059999) is True
    assert candle.is_period_closed(1700000059998) is False

    # 2. Historical candle has UNKNOWN availability without explicit positive latency
    assert candle.effective_available_at_ms(assumed_latency_ms=None) is None
    assert candle.effective_available_at_ms(assumed_latency_ms=0) is None
    assert candle.is_available_at(1700000059999, assumed_latency_ms=None) is False
    assert candle.is_available_at(1700000059999, assumed_latency_ms=0) is False

    # 3. Explicit positive latency (e.g. 1000ms network delay)
    assert candle.effective_available_at_ms(assumed_latency_ms=1000) == 1700000060999
    assert candle.is_available_at(1700000059999, assumed_latency_ms=1000) is False
    assert candle.is_available_at(1700000060999, assumed_latency_ms=1000) is True


def test_observed_live_ingestion_availability():
    candle = Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=1700000000000,
        close_time_ms=1700000059999,
        open=50000.0,
        high=50100.0,
        low=49950.0,
        close=50050.0,
        volume=1.0,
        quote_volume=50000.0,
        trades_count=10,
        taker_buy_base_volume=0.5,
        taker_buy_quote_volume=25000.0,
        observed_ingested_at_ms=1700000060500,  # Arrived 501ms after close
    )
    assert candle.effective_available_at_ms() == 1700000060500
    assert candle.is_available_at(1700000060000) is False
    assert candle.is_available_at(1700000060500) is True


def test_invalid_observed_ingestion_before_close_time():
    with pytest.raises(InvalidCandleError, match="cannot be before close_time_ms"):
        Candle(
            venue="BINANCE",
            symbol="BTCUSDT",
            timeframe="1m",
            open_time_ms=1700000000000,
            close_time_ms=1700000059999,
            open=50000.0,
            high=50100.0,
            low=49950.0,
            close=50050.0,
            volume=1.0,
            quote_volume=50000.0,
            trades_count=10,
            taker_buy_base_volume=0.5,
            taker_buy_quote_volume=25000.0,
            observed_ingested_at_ms=1700000059000,  # Invalid: arrived before candle closed
        )


def test_invalid_candle_high_less_than_low():
    with pytest.raises(InvalidCandleError, match="cannot be lower than low"):
        Candle(
            venue="BINANCE",
            symbol="BTCUSDT",
            timeframe="1m",
            open_time_ms=1700000000000,
            close_time_ms=1700000059999,
            open=50000.0,
            high=49900.0,  # Invalid: high < low
            low=49950.0,
            close=50000.0,
            volume=1.0,
            quote_volume=50000.0,
            trades_count=10,
            taker_buy_base_volume=0.5,
            taker_buy_quote_volume=25000.0,
        )


def test_invalid_candle_negative_volume():
    with pytest.raises(InvalidCandleError, match="volume cannot be negative"):
        Candle(
            venue="BINANCE",
            symbol="BTCUSDT",
            timeframe="1m",
            open_time_ms=1700000000000,
            close_time_ms=1700000059999,
            open=50000.0,
            high=50100.0,
            low=49950.0,
            close=50050.0,
            volume=-1.0,  # Invalid: volume < 0
            quote_volume=50000.0,
            trades_count=10,
            taker_buy_base_volume=0.5,
            taker_buy_quote_volume=25000.0,
        )


def test_invalid_candle_negative_price():
    with pytest.raises(InvalidCandleError, match="Prices must be strictly positive"):
        Candle(
            venue="BINANCE",
            symbol="BTCUSDT",
            timeframe="1m",
            open_time_ms=1700000000000,
            close_time_ms=1700000059999,
            open=-50000.0,
            high=50100.0,
            low=49950.0,
            close=50050.0,
            volume=1.0,
            quote_volume=50000.0,
            trades_count=10,
            taker_buy_base_volume=0.5,
            taker_buy_quote_volume=25000.0,
        )


def test_invalid_candle_close_before_open():
    with pytest.raises(InvalidCandleError, match="must be >= open_time_ms"):
        Candle(
            venue="BINANCE",
            symbol="BTCUSDT",
            timeframe="1m",
            open_time_ms=1700000059999,
            close_time_ms=1700000000000,  # Invalid: close_time < open_time
            open=50000.0,
            high=50100.0,
            low=49950.0,
            close=50050.0,
            volume=1.0,
            quote_volume=50000.0,
            trades_count=10,
            taker_buy_base_volume=0.5,
            taker_buy_quote_volume=25000.0,
        )


def test_quality_inspector_detects_duplicates_and_missing():
    c0 = Candle(
        venue="BINANCE", symbol="BTCUSDT", timeframe="1m",
        open_time_ms=0, close_time_ms=59999,
        open=100.0, high=101.0, low=99.0, close=100.5,
        volume=1.0, quote_volume=100.0, trades_count=1,
        taker_buy_base_volume=0.5, taker_buy_quote_volume=50.0,
    )
    c0_dup = Candle(
        venue="BINANCE", symbol="BTCUSDT", timeframe="1m",
        open_time_ms=0, close_time_ms=59999,
        open=100.0, high=101.0, low=99.0, close=100.5,
        volume=1.0, quote_volume=100.0, trades_count=1,
        taker_buy_base_volume=0.5, taker_buy_quote_volume=50.0,
    )
    c2 = Candle(
        venue="BINANCE", symbol="BTCUSDT", timeframe="1m",
        open_time_ms=120000, close_time_ms=179999,
        open=102.0, high=103.0, low=101.0, close=102.5,
        volume=1.0, quote_volume=102.0, trades_count=1,
        taker_buy_base_volume=0.5, taker_buy_quote_volume=51.0,
    )

    report = QualityInspectorService.inspect(
        candles=[c0, c0_dup, c2],
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe=Timeframe.M1,
        start_time_ms=0,
        end_time_ms=120000,
    )

    assert report.total_expected_intervals == 3
    assert report.total_received_candles == 3
    assert report.valid_candles_count == 2
    assert report.duplicate_candles_count == 1
    assert report.missing_intervals_count == 1
    assert report.is_pristine is False
