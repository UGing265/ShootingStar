"""Binance Spot market data adapter."""

import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from shootingstar.domain.exceptions import DomainError
from shootingstar.domain.models import Candle, Venue

logger = logging.getLogger(__name__)


class BinanceRateLimitError(DomainError):
    """Raised when HTTP 429 or 418 is encountered."""
    pass


class BinanceBannedError(DomainError):
    """Raised when HTTP 418 (IP banned) is encountered. HALT IMMEDIATELY."""
    pass


class BinanceSpotClient:
    """HTTP Client for Binance Spot public klines endpoint."""

    BASE_URL = "https://api.binance.com"
    KLINES_PATH = "/api/v3/klines"

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self.last_used_weight_1m = 0

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> List[List[Any]]:
        """Fetches raw klines from Binance Spot API.
        
        Strictly observes IP weight limits and handles 429 backoff / 418 ban halting.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_time_ms,
            "limit": min(limit, 1000),
        }
        if end_time_ms is not None:
            params["endTime"] = end_time_ms

        url = f"{self.base_url}{self.KLINES_PATH}"
        max_retries = 3

        with httpx.Client(timeout=self.timeout) as client:
            for attempt in range(max_retries):
                response = client.get(url, params=params)

                # Track used weight if provided by Binance header
                weight_header = response.headers.get("x-mbx-used-weight-1m")
                if weight_header and weight_header.isdigit():
                    self.last_used_weight_1m = int(weight_header)

                if response.status_code == 418:
                    logger.critical("HTTP 418 received from Binance: IP banned. Halting immediately.")
                    raise BinanceBannedError("HTTP 418: Binance IP banned. Do not continue making requests.")

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    logger.warning("HTTP 429 rate limit exceeded. Backoff for %s seconds.", retry_after)
                    if attempt < max_retries - 1:
                        time.sleep(retry_after)
                        continue
                    raise BinanceRateLimitError(f"HTTP 429: Rate limit exhausted after {max_retries} attempts.")

                response.raise_for_status()
                return response.json()

        return []

    @staticmethod
    def parse_kline_row(row: List[Any], venue: str, symbol: str, timeframe: str) -> Candle:
        """Parses a raw Binance kline array into a validated domain Candle."""
        return Candle(
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            open_time_ms=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            close_time_ms=int(row[6]),
            quote_volume=float(row[7]),
            trades_count=int(row[8]),
            taker_buy_base_volume=float(row[9]),
            taker_buy_quote_volume=float(row[10]),
        )
