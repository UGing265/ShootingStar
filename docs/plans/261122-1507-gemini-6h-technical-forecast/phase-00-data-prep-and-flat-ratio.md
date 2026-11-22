# Phase 00 — Tải dữ liệu dài + đo tỷ lệ FLAT (Lead)

**Worker:** Lead (orchestrator) · **Ưu tiên:** cao · **Trạng thái:** pending

## Mục tiêu
- Có snapshot nến 1m BTCUSDT từ 2025-02-01 00:00 UTC tới nay (sau knowledge cutoff Gemini 01/2025).
- Đo % mốc 6h có |Δ| < 1% để xác nhận ngưỡng FLAT không loại quá nhiều mẫu.

## Bước
1. Hỏi user xác nhận trước khi tải (khoảng 950k nến, nhiều request Binance).
2. `cd backend && .venv/Scripts/shootingstar fetch-history --timeframe 1m --start 2025-02-01T00:00:00 --end <now>` (nếu lệnh giới hạn cửa sổ, chia theo tháng).
3. `shootingstar list-snapshots` ghi lại snapshot id/hash, kiểm gap report.
4. Script tạm trong scratchpad (không commit): đọc parquet, lấy mốc mỗi 6h, tính |close(t+6h)/close(t) − 1|, in % < 1%, < 0.5%.

## Nghiệm thu
- Snapshot tồn tại, quality report không gap lớn chưa giải thích.
- Có con số % FLAT thật; báo user nếu > 60%.

## Rủi ro
- Rate limit Binance → ingestion đã có backoff; chia nhỏ cửa sổ.
- Dung lượng parquet lớn → chấp nhận, local-first.
