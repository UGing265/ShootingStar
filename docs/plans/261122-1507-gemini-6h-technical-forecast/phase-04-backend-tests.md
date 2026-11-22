# Phase 04 — Test backend

**Worker:** command-code flash · **Phụ thuộc:** 02 (phần pure), 03 (phần pipeline) · **Trạng thái:** pending

## File sở hữu
- Tạo: `backend/tests/test_forecast_indicators.py`, `test_forecast_digest.py`, `test_forecast_baselines_outcome.py`, `backend/tests/fakes/fake_gemini_forecast.py` (nếu omp chưa tạo).
- Sửa: `backend/tests/test_external_analysis.py` (1033 dòng: bỏ test hypothesis/research/grounding đã xoá, thêm test pipeline mới; tách file nếu > 400 dòng).

## Test bắt buộc
- Indicators: EMA/RSI/MACD/ATR trên chuỗi nhỏ tính tay (ghi giá trị kỳ vọng + cách tính trong comment).
- Resample 1m → 15m/1h đúng OHLCV; bucket chưa đóng tại t bị loại.
- Lookahead: thêm nến sau t không đổi digest/digest_hash.
- Thiếu lịch sử → `InsufficientHistoryError`.
- Baselines: always_up luôn UP; momentum_6h UP/DOWN/None đúng.
- Outcome: +1.5% → UP, −1.2% → DOWN, +0.4% → FLAT, thiếu nến → UNSCORABLE.
- `possible_memorization`: t 2024-12 → True, t 2025-03 → False.
- Pipeline (fake Gemini ở tầng transport): đúng 1 call; answer schema sai → status lỗi; reason trỏ feature_id không tồn tại → cờ verification; envelope đủ field.
- API: tạo job 6h qua route (admin gate bật), reveal dùng ngưỡng 1%.

## Ràng buộc
- Không gọi mạng thật. Fake chỉ trong `tests/`. Không sửa code production (báo Lead nếu thấy bug).

## Nghiệm thu
- `cd backend && .venv/Scripts/python -m pytest` exit 0, dán số passed.
