"""Synthetic 1m candle fixtures for forecast pipeline and API tests (no network, no DB)."""

import uuid

from shootingstar.domain.models import Candle

MINUTE_MS = 60_000
# 207 continuous hourly bars is the digest warm-up minimum.
WARMUP_MINUTES = 207 * 60
# Aligned to 4h so 1m/15m/1h/4h resampling stays continuous; after the model cutoff.
BASE_START_MS = 1_800_000_000_000


def make_1m_candle(open_time_ms, close, volume=1.0):
    return Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=open_time_ms,
        close_time_ms=open_time_ms + MINUTE_MS - 1,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
        quote_volume=volume * close,
        trades_count=10,
        taker_buy_base_volume=volume / 2,
        taker_buy_quote_volume=volume * close / 2,
    )


def make_series(start_ms, minutes, base=50_000.0, step=0.5):
    return [make_1m_candle(start_ms + i * MINUTE_MS, base + i * step) for i in range(minutes)]


def unique_start_ms():
    """Unique, 4h-aligned start so snapshot hashes never collide across test runs."""
    return BASE_START_MS + (uuid.uuid4().int % 10_000) * 14_400_000
