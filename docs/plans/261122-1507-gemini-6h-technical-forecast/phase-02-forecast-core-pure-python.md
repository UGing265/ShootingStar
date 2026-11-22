# Phase 02 — Lõi dự báo Python thuần (không gọi Gemini)

**Worker:** omp terra · **Ưu tiên:** cao · **Trạng thái:** pending

## Bối cảnh
- Đọc: `docs/plans/261122-1507-gemini-6h-technical-forecast/reports/brainstorm-261122-1419-gemini-6h-technical-forecast.md`, `backend/shootingstar/application/external_analysis/context.py` (causal window hiện có, `InsufficientHistoryError`), `domain/` model `Candle`, `application/patterns.py` (mẫu nến có sẵn, tái sử dụng nếu hợp).

## File tạo mới (package `backend/shootingstar/application/forecast/`)
- `__init__.py`
- `resample.py`: gộp nến 1m/5m đã đóng thành 15m/1h; bỏ bucket chưa đủ nến hoặc chưa đóng tại t.
- `indicators.py`: numpy thuần: `ema`, `rsi(14)`, `macd(12,26,9)`, `atr(14)`, volume ratio (vol cuối / TB 20). Docstring công thức.
- `technical_digest.py`: `build_technical_digest(candles, t_ms, lookback_days=14) -> TechnicalDigest`; mỗi feature `{feature_id, timeframe, name, value, unit}`: EMA20/50 slope 1h & 4h (4h gộp từ 1h), RSI 1h & 15m, MACD hist 1h, ATR% 1h, volume ratio 1h, vị trí giá trong range 24h & 7d (0..1), swing high/low gần nhất 1h, return 6h/24h. Thiếu lịch sử → `InsufficientHistoryError`. Kèm `digest_hash`.
- `agreement_score.py`: đếm feature chiều UP vs DOWN theo quy tắc cố định ghi trong docstring (vd slope>0 = UP, RSI>50 = UP, MACD hist>0 = UP, return 6h>0 = UP); trả `{up: n, down: m, total: k}`.
- `baselines.py`: `always_up() -> "UP"`; `momentum_6h(candles, t_ms) -> "UP"|"DOWN"|None` (close(t) vs close(t−6h)).
- `outcome.py`: `evaluate_direction_outcome(candles, t_ms, horizon_minutes, purchase_price, flat_threshold_pct=1.0) -> {outcome: UP|DOWN|FLAT|UNSCORABLE, target_price, move_pct}` (dùng interval containment như `reveal_outcome` hiện tại).
- `memorization_flag.py` (hoặc hằng trong `outcome.py` nếu <10 dòng): `MODEL_KNOWLEDGE_CUTOFF_MS` cho gemini-2.5-flash = 2025-02-01 UTC; `possible_memorization(t_ms, model_id) -> bool`.

## Ràng buộc
- Mỗi file < 200 dòng, kebab không áp cho Python module (dùng snake_case theo Python).
- Không thêm dependency. Không gọi mạng. Không đổi DB schema.
- Chỉ dùng nến `close_time_ms <= t`.

## Nghiệm thu
- `python -c "import shootingstar.application.forecast"` OK; `pytest` hiện có không vỡ.
- Digest JSON cho 1 mốc thật trên snapshot `61da7964…` < ~2k token (đếm ký tự /4).
- Tự viết 1 test nhỏ cho lookahead (feature không đổi khi thêm nến sau t) — test đầy đủ ở phase 04.

## Kết thúc
`Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT` + 1-2 dòng.
