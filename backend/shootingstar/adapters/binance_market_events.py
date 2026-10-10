"""Public Binance Spot market events and exchange rules adapter.

STRICT INVARIANTS:
1. Strictly public market data: ZERO private/signed trading keys required or accepted.
2. Symbol filters parsed dynamically from /api/v3/exchangeInfo (tickSize, stepSize, minNotional, minQty).
3. Respects rate limits (x-mbx-used-weight-1m), Retry-After on HTTP 429, and halts immediately on HTTP 418.
4. Causal timestamps: records local received_at_ms alongside exchange event time.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import httpx

from shootingstar.adapters.binance import (
    BinanceBannedError,
    BinanceRateLimitError,
    BinanceTimeoutError,
)
from shootingstar.domain.trade_plan import SymbolFilters

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublicTradeEvent:
    trade_id: int
    symbol: str
    price: Decimal
    quantity: Decimal
    event_time_ms: int
    is_buyer_maker: bool
    received_at_ms: int


@dataclass(frozen=True)
class PublicBookDepthSnapshot:
    symbol: str
    last_update_id: int
    bids: Tuple[Tuple[Decimal, Decimal], ...]  # (price, qty)
    asks: Tuple[Tuple[Decimal, Decimal], ...]  # (price, qty)
    received_at_ms: int


class BinanceMarketEventsClient:
    """Client for public exchangeInfo, trades, and orderbook depth."""

    BASE_URL = "https://api.binance.com"

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self.last_used_weight_1m = 0

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        max_retries = 3

        with httpx.Client(timeout=self.timeout) as client:
            for attempt in range(max_retries):
                try:
                    response = client.get(url, params=params)
                except httpx.TimeoutException as exc:
                    logger.warning("Binance Spot request timeout on attempt %d/%d: %s", attempt + 1, max_retries, exc)
                    if attempt < max_retries - 1:
                        time.sleep(1.0)
                        continue
                    raise BinanceTimeoutError(f"Request to {endpoint} timed out.") from exc

                weight_header = response.headers.get("x-mbx-used-weight-1m")
                if weight_header and weight_header.isdigit():
                    self.last_used_weight_1m = int(weight_header)

                if response.status_code == 418:
                    logger.critical("HTTP 418 IP banned from Binance. Halting.")
                    raise BinanceBannedError("HTTP 418: Binance IP banned.")

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "5"))
                    logger.warning("HTTP 429 rate limit exceeded. Backoff %ds.", retry_after)
                    if attempt < max_retries - 1:
                        time.sleep(retry_after)
                        continue
                    raise BinanceRateLimitError("HTTP 429: Rate limit exceeded.")

                response.raise_for_status()
                return response.json()

        raise BinanceTimeoutError(f"Failed to fetch {endpoint} after {max_retries} attempts.")

    def fetch_symbol_filters(self, symbol: str = "BTCUSDT") -> SymbolFilters:
        """Dynamically parses price and lot size filters from exchangeInfo."""
        data = self._request("/api/v3/exchangeInfo", params={"symbol": symbol})
        symbols = data.get("symbols", [])
        if not symbols:
            raise ValueError(f"Symbol {symbol} not found in exchangeInfo response.")

        sym_info = symbols[0]
        filters = sym_info.get("filters", [])

        tick_size: Optional[Decimal] = None
        step_size: Optional[Decimal] = None
        min_qty: Optional[Decimal] = None
        min_notional: Optional[Decimal] = None

        for f in filters:
            ftype = f.get("filterType")
            if ftype == "PRICE_FILTER":
                tick_size = Decimal(str(f["tickSize"]))
            elif ftype == "LOT_SIZE":
                step_size = Decimal(str(f["stepSize"]))
                min_qty = Decimal(str(f["minQty"]))
            elif ftype in ("NOTIONAL", "MIN_NOTIONAL"):
                min_val = f.get("minNotional")
                if min_val is not None:
                    min_notional = Decimal(str(min_val))

        if tick_size is None or step_size is None:
            raise ValueError(f"Incomplete filters returned for {symbol}: {filters}")

        return SymbolFilters(
            symbol=symbol,
            tick_size=tick_size,
            step_size=step_size,
            min_notional=min_notional if min_notional is not None else Decimal("0"),
            min_qty=min_qty if min_qty is not None else Decimal("0"),
        )

    def fetch_recent_trades(self, symbol: str = "BTCUSDT", limit: int = 100) -> List[PublicTradeEvent]:
        """Fetches recent public executed trades with local receipt timestamp."""
        received_at = int(time.time() * 1000)
        data = self._request("/api/v3/trades", params={"symbol": symbol, "limit": limit})
        trades: List[PublicTradeEvent] = []
        for t in data:
            trades.append(
                PublicTradeEvent(
                    trade_id=int(t["id"]),
                    symbol=symbol,
                    price=Decimal(str(t["price"])),
                    quantity=Decimal(str(t["qty"])),
                    event_time_ms=int(t["time"]),
                    is_buyer_maker=bool(t["isBuyerMaker"]),
                    received_at_ms=received_at,
                )
            )
        return trades

    def fetch_order_book_depth(self, symbol: str = "BTCUSDT", limit: int = 20) -> PublicBookDepthSnapshot:
        """Fetches top-of-book depth for execution cost evidence."""
        received_at = int(time.time() * 1000)
        data = self._request("/api/v3/depth", params={"symbol": symbol, "limit": limit})
        bids = tuple((Decimal(str(p)), Decimal(str(q))) for p, q in data.get("bids", []))
        asks = tuple((Decimal(str(p)), Decimal(str(q))) for p, q in data.get("asks", []))
        return PublicBookDepthSnapshot(
            symbol=symbol,
            last_update_id=int(data["lastUpdateId"]),
            bids=bids,
            asks=asks,
            received_at_ms=received_at,
        )
