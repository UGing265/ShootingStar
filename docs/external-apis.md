# External APIs Integration Register

This document registers external API integrations used by ShootingStar, including endpoint details, rate limits, weight tracking, and error handling.

---

## 1. Binance Spot Public Market Data

ShootingStar uses Binance Spot public market data for BTCUSDT candle research. **No trading API key or authentication is required or used.**

### Endpoint Specification
- **Base URL:** `https://api.binance.com`
- **Path:** `GET /api/v3/klines`
- **Method:** `GET`
- **Authentication:** None (Public endpoint)

### Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `symbol` | STRING | YES | E.g. `BTCUSDT` |
| `interval` | STRING | YES | E.g. `1m`, `5m` |
| `startTime` | LONG | NO | Start time in UTC milliseconds (inclusive) |
| `endTime` | LONG | NO | End time in UTC milliseconds (inclusive) |
| `timeZone` | STRING | NO | Default `0` (UTC) |
| `limit` | INT | NO | Default 500, max 1000 candles per request |

### Response Schema
Array of candle arrays:
```json
[
  [
    1499040000000,      // 0: Kline open time (ms UTC)
    "0.01634790",       // 1: Open price
    "0.80000000",       // 2: High price
    "0.01575800",       // 3: Low price
    "0.01577100",       // 4: Close price
    "148976.11427815",  // 5: Volume
    1499644799999,      // 6: Kline close time (ms UTC)
    "2434.19055334",    // 7: Quote asset volume
    308,                // 8: Number of trades
    "1756.87402397",    // 9: Taker buy base asset volume
    "28.46694368",      // 10: Taker buy quote asset volume
    "0"                 // 11: Unused field
  ]
]
```

### Rate Limits & Weight Management
- **IP Weight Budget:** Binance Spot allows 1200 request weight per minute per IP.
- `GET /api/v3/klines` has a weight of **2** per request.
- **Headers to monitor:**
  - `x-mbx-used-weight-1m`: Cumulative IP weight used in the current 1-minute window.
  - `Retry-After`: Seconds to wait when rate-limited.
- **HTTP 429:** IP weight limit reached. Backoff exponentially and respect `Retry-After`.
- **HTTP 418:** IP auto-banned due to continued calls after 429. **MUST immediately halt and raise a critical error.** Never continue issuing requests upon HTTP 418.

### Data Invariants & Quality Rules
1. **Timestamp format:** All timestamps strictly converted to UTC ISO 8601 / POSIX integer milliseconds.
2. **Current unclosed candle:** If `close_time > now_utc_ms`, the candle is still forming and **MUST be dropped** from immutable snapshots.
3. **Pagination:** Ordered chronological pagination by `startTime = last_open_time + 1`. Deduplication by `(venue, symbol, timeframe, open_time)`.
4. **Retention:** Exact raw JSON responses stored in raw archive with checksums. Validated candles stored immutably.

---

## 2. Gemini Grounding with Google Search (Evidence Analysis)

Used in the multi-stage evidence analysis pipeline (`ExternalAnalysisService`) for preliminary hypothesis research and pattern criterion verification.

### Endpoint & Model Specification
- **Endpoint:** `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- **Default Model:** `gemini-2.5-flash`
- **Authentication:** API key via query parameter (`?key=...`) or header managed by `APIKeyManager` / budget tracker.
- **Feature:** Grounding tool `google_search` (`tools: [{"googleSearch": {}}]`).

### Response Parsing & Grounding Metadata
- Captures `candidates[0].groundingMetadata`:
  - `webSearchQueries`: Exact queries executed by Google Search.
  - `groundingChunks`: Retrieved web source references with URIs and page titles.
  - `groundingSupports`: Segments linked to citation chunk indices.
- Fallback mode: If grounded model returns text rather than structured JSON, a two-step parse (search extraction + criteria extraction) is executed.

### Operational & Safety Guards
1. **Lookahead / Hindsight Guard:** Search queries must strictly target definitions, methodology, or pattern rules. Never search for future BTC prices post-`t` or historical outcome labels.
2. **URL & SSRF Validation:** Retrieved source URLs fetched for excerpt extraction must pass `url_validator.validate_public_https_url`.
3. **Budget & Quota Management:** Grounded calls consume tracked quota. Incomplete or quota-exceeded searches transition job cleanly to `RESEARCH_INCOMPLETE` without fabricating fake evidence.
