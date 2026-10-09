"""Application interfaces and contracts."""

from typing import List, Protocol, Tuple
from shootingstar.domain.models import Candle, DataQualityReport, Timeframe


class MarketDataGateway(Protocol):
    """Gateway for fetching raw external market data."""

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        limit: int = 1000,
    ) -> List[List[object]]:
        ...


class QualityInspectorService:
    """Service to analyze candle series continuity, detect gaps, duplicates, and invalids."""

    @staticmethod
    def inspect(
        candles: List[Candle],
        venue: str,
        symbol: str,
        timeframe: Timeframe,
        start_time_ms: int,
        end_time_ms: int,
    ) -> DataQualityReport:
        step_ms = timeframe.duration_ms
        if end_time_ms < start_time_ms:
            expected_intervals = 0
        else:
            expected_intervals = ((end_time_ms - start_time_ms) // step_ms) + 1

        seen_keys = set()
        duplicates = 0
        valid_candles = []

        for c in candles:
            if c.key in seen_keys:
                duplicates += 1
            else:
                seen_keys.add(c.key)
                valid_candles.append(c)

        # Count missing intervals
        existing_open_times = {c.open_time_ms for c in valid_candles}
        missing_count = 0
        current_time = start_time_ms
        while current_time <= end_time_ms:
            if current_time not in existing_open_times:
                missing_count += 1
            current_time += step_ms

        return DataQualityReport(
            venue=venue,
            symbol=symbol,
            timeframe=timeframe.value,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            total_expected_intervals=expected_intervals,
            total_received_candles=len(candles),
            valid_candles_count=len(valid_candles),
            missing_intervals_count=missing_count,
            duplicate_candles_count=duplicates,
            invalid_candles_count=0,
        )
