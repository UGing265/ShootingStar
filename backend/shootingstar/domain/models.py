"""Domain models for market data and research invariants.

STRICT INVARIANT: No dependencies on FastAPI, SQLAlchemy, pandas, or exchange SDKs.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple


class Venue(str, Enum):
    BINANCE = "BINANCE"


class Symbol(str, Enum):
    BTCUSDT = "BTCUSDT"


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"

    @property
    def duration_ms(self) -> int:
        if self == Timeframe.M1:
            return 60 * 1000
        elif self == Timeframe.M5:
            return 5 * 60 * 1000
        raise ValueError(f"Unknown timeframe duration for {self}")


@dataclass(frozen=True)
class Provenance:
    source: str
    endpoint: str
    ingested_at_ms: int
    raw_checksum_sha256: str


@dataclass(frozen=True)
class Candle:
    venue: str
    symbol: str
    timeframe: str
    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades_count: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float
    observed_ingested_at_ms: Optional[int] = None
    is_backfill: bool = False

    def __post_init__(self) -> None:
        from shootingstar.domain.exceptions import InvalidCandleError

        if self.open_time_ms < 0:
            raise InvalidCandleError(f"open_time_ms cannot be negative: {self.open_time_ms}")
        if self.close_time_ms < self.open_time_ms:
            raise InvalidCandleError(
                f"close_time_ms ({self.close_time_ms}) must be >= open_time_ms ({self.open_time_ms})"
            )
        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise InvalidCandleError(
                f"Prices must be strictly positive: open={self.open}, high={self.high}, low={self.low}, close={self.close}"
            )
        if self.high < self.low:
            raise InvalidCandleError(f"high ({self.high}) cannot be lower than low ({self.low})")
        if self.high < self.open or self.high < self.close:
            raise InvalidCandleError(
                f"high ({self.high}) must be >= open ({self.open}) and close ({self.close})"
            )
        if self.low > self.open or self.low > self.close:
            raise InvalidCandleError(
                f"low ({self.low}) must be <= open ({self.open}) and close ({self.close})"
            )
        if self.volume < 0:
            raise InvalidCandleError(f"volume cannot be negative: {self.volume}")
        if self.trades_count < 0:
            raise InvalidCandleError(f"trades_count cannot be negative: {self.trades_count}")
        if self.observed_ingested_at_ms is not None:
            if self.observed_ingested_at_ms < self.close_time_ms:
                raise InvalidCandleError(
                    f"observed_ingested_at_ms ({self.observed_ingested_at_ms}) cannot be before close_time_ms ({self.close_time_ms})"
                )

    @property
    def key(self) -> Tuple[str, str, str, int]:
        """Unique natural key for deduplication and canonical storage."""
        return (self.venue, self.symbol, self.timeframe, self.open_time_ms)

    def is_period_closed(self, timestamp_ms: int) -> bool:
        """Checks if the candle timeframe interval has finished by timestamp_ms.
        
        INVARIANT: Interval closure does NOT equal historical availability.
        """
        return timestamp_ms >= self.close_time_ms

    def effective_available_at_ms(self, assumed_latency_ms: Optional[int] = None) -> Optional[int]:
        """Returns the timestamp when this candle was actually available or assumed available.
        
        Rules:
        - If backfilled (is_backfill is True or observed_ingested_at_ms is None), requires assumed_latency_ms > 0.
        - If observed live (is_backfill is False and observed_ingested_at_ms is not None), returns observed_ingested_at_ms.
        - If assumed_latency_ms is None or <= 0 for backfilled candle, returns None (availability unknown).
        """
        if self.is_backfill or self.observed_ingested_at_ms is None:
            if assumed_latency_ms is None or assumed_latency_ms <= 0:
                return None
            return self.close_time_ms + assumed_latency_ms
        return self.observed_ingested_at_ms

    def is_available_at(self, timestamp_ms: int, assumed_latency_ms: Optional[int] = None) -> bool:
        """Determines if the candle was available to an observer at timestamp_ms.
        
        Returns False if availability timestamp is unknown.
        """
        avail_ms = self.effective_available_at_ms(assumed_latency_ms=assumed_latency_ms)
        if avail_ms is None:
            return False
        return timestamp_ms >= avail_ms

    @property
    def open_time_utc(self) -> datetime:
        return datetime.fromtimestamp(self.open_time_ms / 1000.0, tz=timezone.utc)

    @property
    def close_time_utc(self) -> datetime:
        return datetime.fromtimestamp(self.close_time_ms / 1000.0, tz=timezone.utc)


@dataclass(frozen=True)
class DataQualityReport:
    venue: str
    symbol: str
    timeframe: str
    start_time_ms: int
    end_time_ms: int
    total_expected_intervals: int
    total_received_candles: int
    valid_candles_count: int
    missing_intervals_count: int
    duplicate_candles_count: int
    invalid_candles_count: int

    @property
    def coverage_ratio(self) -> float:
        if self.total_expected_intervals == 0:
            return 1.0
        return self.valid_candles_count / self.total_expected_intervals

    @property
    def is_pristine(self) -> bool:
        return (
            self.missing_intervals_count == 0
            and self.duplicate_candles_count == 0
            and self.invalid_candles_count == 0
            and self.valid_candles_count == self.total_expected_intervals
        )
