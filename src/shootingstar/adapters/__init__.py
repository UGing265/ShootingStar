"""Adapters package."""

from shootingstar.adapters.binance import (
    BinanceBannedError,
    BinanceRateLimitError,
    BinanceSpotClient,
)

__all__ = [
    "BinanceBannedError",
    "BinanceRateLimitError",
    "BinanceSpotClient",
]
