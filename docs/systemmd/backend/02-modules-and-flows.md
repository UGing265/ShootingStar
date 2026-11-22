# Backend: module và luồng chính

Tóm tắt từ code. Chưa chạy end to end vì cần PostgreSQL.

## 1. Ingestion (lấy nến Binance)

1. `POST /ingestion/preview`: lấy mẫu nhỏ từ `GET https://api.binance.com/api/v3/klines`, ước lượng, cấp token xem trước. Không lưu gì.
2. `POST /ingestion/jobs`: cần token, tạo job chạy nền, trả `202`. Hỏi tình trạng bằng `GET /ingestion/jobs/{id}`.
3. `application/ingestion.py` (`run_pilot`): lặp lấy tối đa 1000 nến mỗi lần, lưu byte phản hồi gốc, đổi thành `Candle`, bỏ nến ngoài khoảng và nến chưa đóng, nghỉ ngắn giữa các lần.
4. Kiểm tra chất lượng (thiếu, trùng, lệch giờ), ghi snapshot Parquet bất biến (id là SHA-256 của file) và bản ghi `ingestion_runs`, `snapshots`.
5. Lỗi Binance: timeout thì thử lại; `429` báo giới hạn; `418` dừng ngay.

CLI tương đương: `fetch-pilot`, `fetch-history`.

## 2. Replay (mô phỏng chiến thuật offline)

- `POST /replay/jobs` tạo job từ snapshot và mốc `t`; chỉ dùng nến `available_at <= t`.
- `POST /replay/jobs/{id}/vote` rồi `/reveal`: người dùng vote trước khi mở kết quả; vote không sửa lại.
- Engine chỉ chấm `strategy_evaluation` (`entry_strategy`, `barrier_evaluation`). Trường `ai_prediction` luôn là `NO_MODEL`: hướng AI chỉ đến từ báo cáo Gemini.
- Kết quả lưu thành file JSON trong thư mục simulations, không phải bảng DB.

## 3. Báo cáo Gemini (`external_analysis/`)

- `POST /external-analysis/jobs`: tạo job nền (`202`), nhiều tầng: dựng ngữ cảnh nhân quả (`context.py`), gọi Gemini qua `adapters/model_api/gemini_adapter.py` (xoay key, retry `503` với backoff), kiểm tra (`verifier.py`), trình bày (`report_presentation.py`).
- Có `vote` và `reveal` riêng. Kết quả lưu ở bảng `external_analysis_jobs`.
- `patterns.evaluate_pattern_diagnostics` sinh tiêu chí nến đính kèm báo cáo (không có thống kê hay lợi nhuận).
- Cổng bảo vệ: `SHOOTINGSTAR_EXTERNAL_API_ENABLED`, `SHOOTINGSTAR_ADMIN_KEY`.

## 4. Trade plan / watch

- `trade_watch.py`, `entry_strategy.py`, `barrier_evaluation.py`, `domain/trade_plan.py`; routes ở `trade_plan_routes.py` (`/trade-watches`, `/trade-plans/{id}/entry-observations`, `/exit-observations`).
- CLI `watch-entry`. Hiện chưa có trang frontend dùng nhóm này. Chưa được coi là chức năng nghiệm thu (xem `AGENTS.md`).

## 5. Quan hệ giữa replay và báo cáo

Hai job độc lập, hai nơi lưu. Frontend (`use-replay-session.ts`) cho người dùng chọn engine `strategy` hoặc `gemini`, rồi có thể thêm engine còn lại tại cùng mốc; vote/reveal được gửi cho job nào tồn tại. Chưa hợp nhất contract.
